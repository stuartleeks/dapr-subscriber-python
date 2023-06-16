# subscriber-sdk-simplified

## Overview

The `PubSub` folder contains the `ConsumerApp` class which contains the logic to hook up subscribers to Service Bus Topic Subscriptions. 
It uses a convention-based approach to determine the topic name name to use.
It also provides a way to customise the topic name and subscriber name if needed.

The `ConsumerApp` class provides a `consume` decorator that can be used to register a function as a subscriber.
This can be used to register a function as a subscriber to a topic:

```python
consumer_app = ConsumerApp()

# Event model for the task-created event
class TaskCreatedStateChangeEvent(BaseModel):
    # Add any task-created event properties here
    pass


# Consumer function that will be registered as a subscriber to the task-created topic
@consumer_app.consume
async def on_task_created(notification: TaskCreatedStateChangeEvent):
    print(f"🔔 new task created event: {state_changed_event}")
    return ConsumerResult.SUCCESS

# Invoke consumer app to run the subscriber (only needed once per app regardless of number of subscribers)
asyncio.run(consumer_app.run())
```

In the example above, the `on_task_created` function will be registered as a subscriber to the `task-created` topic (based on the method name).

The  previous example use a common Service Bus subscription name across topics.
This means that you cannot have multiple subscribers for the same event type in the same app using this approach.
However, the `consume` method allows you to specify a custom subscription name to use:

```python
# Consumer function that will be registered as a subscriber to the task-created topic 
# using the default subscription name for the app
@consumer_app.consume
async def on_task_created(notification: TaskCreatedStateChangeEvent):
    print(f"🔔 new task created event: {state_changed_event}")
    return ConsumerResult.SUCCESS

# Consumer function that will be registered as a subscriber to the task-created topic
# using a custom subscription name
# NOTE: here we specifiy the topic name as well as the subscription name as the method name 
# was amended to avoid clashing with the above method. If the original method name is used
# (i.e. the methods are in different scopes) then the topic name will be inferred from the method name
@consumer_app.consume(topic_name="task-created", subscription_name="my-custom-subscription")
async def on_task_created2(notification: TaskCreatedStateChangeEvent):
    print(f"🔔 new task created event: {state_changed_event}")
    return ConsumerResult.SUCCESS
```

## How it works

The `ConsumerApp` class provides the `consume` decorator that can be used to register a function as a subscriber.
When the decorator is applied, the `ConsumerApp` inspects the function signature to determine the type of the notification that the subscriber is interested in (with decorator args that can override the conventions used).
The decorator also registers the function as a subsciber to the associated topic/subscription.

When the `run` method is invoked, the `ConsumerApp` creates a connection to Service Bus and creates message receivers for each subscription.
By default, the `run` method will create a subscriber handler for each registered subscriber method.
This can be changed by passing a `filter` arg to the `run` method, or by setting the `SUBSCRIBER_FILTER` environment variable.

Each message subscriber handler runs in its own CoRoutine and calls the associated receiver to get messages to process. 
The number of messages to retrieve in each batch, and the maximum time to wait before messages are returned are both configurable.
When the subscriber handler retrieves message, it does so with a peek-lock (the receiver registers messages with a lock renewal handler that renews the message lock for a configurable period of time).
After registering messages with the lock renewal handler, the subscriber handler passes each message to the subscriber function.
This is done using asyncio to enable concurrent processing of messages.

When the subscriber function returns, the subscriber handler checks the result (`ConsumerResult` enum has `SUCCESS`, `RETRY`, `DROP` values) and uses this to determine whether to complete, abandon or dead-letter the message.
If the handler raises an exception during processing, this is treated as `RETRY` and will abandon the message so that delivery is re-attempted (subject to the maximum delivery count specified in Service Bus).

### Graceful shutfown

When the `run` method is called, it registers a `SIG_TERM` handler. When a `SIG_TERM` signal is received, the `cancel` method it called.
Calling `cancel` sets a flag that the subscriber handlers check before receiving new messages.
Once the handlers have finished processing the current batch of messages, they will exit.
When all handlers have exited, the `run` method will also exit.

The result of this is that there are two factors that control how long it takes for the `run` method to exit: the maximum wait time when receiving messages, and the time it takes for messages to be processed.
If graceful shutdown is desired, it is important that configuration is set so that the pod's `terminationGracePeriod` is a longer duration than the maximum time for the `run` method to exit after a `SIG_TERM` signal is received.


## Configuration

There are various options that can be applied to change the behaviour of the consumer.


| Environment Variable         | Description                                                                                                                                                                                                                                                                              |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AZURE_CLIENT_ID`            | The client id to use to connect to Service Bus (when using workload identity)                                                                                                                                                                                                            |
| `AZURE_TENANT_ID`            | The tenant id associated with AZURE_CLIENT_ID (when using workload identity)                                                                                                                                                                                                             |
| `AZURE_AUTHORITY_HOST`       | The authority host (when using workload identity)                                                                                                                                                                                                                                        |
| `AZURE_FEDERATED_TOKEN_FILE` | The location of the token file (when using workload identity)                                                                                                                                                                                                                            |
| `SERVICE_BUS_NAMESPACE`      | The namespace for the Service Bus to connect to, e.g. `mysb.servicebus.windows.net` (when using workload identity)                                                                                                                                                                       |
| `CONNECTION_STR`             | The connection string for the Service Bus (when _not_ using workload identity, e.g. local dev)                                                                                                                                                                                           |
| `MAX_MESSAGE_COUNT`          | The maxiumum number of messages to receive per batch (defaults to 10). Can be overridden via the `consume` decorator.                                                                                                                                                                    |
| `MAX_WAIT_TIME`              | The maxiumum time in seconds to wait when receiving messages (defaults to 30s). Can be overridden via the `consume` decorator.                                                                                                                                                           |
| `MAX_LOCK_RENEWAL_DURATION`  | The maximum time in seconds to renew each message for during processing this should be at least as long as the anticipated processing time for a message (defaults to 300s). Can be overridden via the `consume` decorator.                                                              |
| `SUBSCRIBER_FILTER`          | The filter to apply to subscribers - this allows an app to register multiple subscribers but run a subset of them when deployed. Defaults to `None` (i.e. run all). Can Can be overridden via the `run` method. The value is a comma-separated list of filters in the form `<topic-name> | <subscription-name>`, e.g. `task-created | subscriber1` |


### Example manifest

The following manifest shows how to deploy the subscriber app to Kubernetes using workload identity:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: subscriber-sdk-simplified
  labels:
    app: subscriber-sdk-simplified
spec:
  replicas: 1
  selector:
    matchLabels:
      app: subscriber-sdk-simplified
  template:
    metadata:
      labels:
        app: subscriber-sdk-simplified
        azure.workload.identity/use: "true" # opt in to workload identity
    spec:
      serviceAccountName: subscriber-sdk-simplified
      containers:
      - name: subscriber-sdk-simplified
        image: myreg.azurecr.net/subscriber-sdk-simplified:latest
        env:
        env:
          # AZURE_CLIENT_ID etc are set by workload identity
          - name: SERVICE_BUS_NAMESPACE
            value: mysb.servicebus.windows.net
          - name: DEFAULT_SUBSCRIPTION_NAME
            value: subscriber-sdk-simplified
          - name: MAX_MESSAGE_COUNT # override the default max messages per batch
            value: "25"
        imagePullPolicy: Always
```

