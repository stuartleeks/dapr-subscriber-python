# python-service-bus-subscribers

This repo is a sample showing how to consume messages from Azure Service Bus using Python. Additionally, it includes an exploration of ways to abstract away large parts of the considerations to simplify the developer experience for consuming messages using a combination of helper code and conventions. 


## Deploying the sample

To deploy the sample:
- open the folder using Visual Studio Code and the Dev Containers extension (this will build a containerised development environment with all the dependencies installed)
- in VS Code terminal, run `az login` to sign in to your Azure account
- copy the `sample.env` file to `.env` and update the values
- run `just deploy` and grab a coffee ☕. This will deploy a container registry, kubernetes cluster, install Dapr, 

## Repo contents

Within the repo, you'll find:
- `src` folder containing the sample code
- `infra` folder containing Bicep to deploy the sample to Azure
- `scripts` folder containing helper scripts to configure/deploy the sample

Under `src` there are several folders:
- `publisher` contains the code for the publisher that sends messages to Service Bus
- `subscriber-dapr-api` contains the code for the subscriber using the Dapr API directly
- `subscriber-dapr-simplified` contains the code for the simplified subscriber code using helper code to simplify the Dapr usage
- `subscriber-sdk-direct` contains the code for the subscriber that directly uses the Service Bus SDK
- `subscriber-sdk-simplified` contains the code for the simplified subscriber code using helper code to simplify the Service Bus SDK usage

## Running locally

If you want to run the code locally, you can also do that. You may want to scale the deployments in the kubernetes cluster to 0 to avoid competing for messages to process 🙂.

To set up your local Dapr environment, run `dapr init`

To run the code:
- run `just run-subscriber-dapr-api` to run the subscriber that uses the Dapr API directly
- run `just run-subscriber-dapr-simplified` to run the subscriber that uses the helper code with Dapr
- run `just run-subscriber-sdk-direct` to run the subscriber that uses the Service Bus SDK directly
- run `just run-subscriber-sdk-simplified` to run the subscriber that uses the helper code with the Service Bus SDK
- run `just run-publisher` to run the publisher that sends messages to the `task-notifications` topic

## Helper code - Dapr

### Overview

In the `subscriber-dapr-simplified` folder, you'll find a `consumer_app.py` file under the `PubSub` folder that contains the helper code.
This is an experiment, but the idea is to provide a simple way to consume messages using Dapr pubsub without having to worry about the details of the Dapr API.

The `ConsumerApp` class provides a simple way to register functions as subscribers to topics.
It uses a convention-based approach to determine the topic name and pubsub component name to use.
It also provides a way to customise the topic name and pubsub component name if needed.


The default pubsub component used for subscriptions is configured to create subscriptions if they do not exist.
This is a convenience feature, but it does require the pubsub component to have `Manage` permissions on the topic.
This is a security consideration that you should take into account when using this approach.
You can disable this feature by setting `disableEntityManagement` to `true` in the Dapr pubsub component configuration.

The `ConsumerApp` class provides a `consume` decorator that can be used to register a function as a subscriber.
This can be used to register a function as a subscriber to a topic:

```python
app = FastAPI()
consumer_app = ConsumerApp(
    app,
    default_pubsub_name="notifications-pubsub-subscriber"
)

# We can consume raw cloud events:
@consumer_app.consume
async def on_task_notification(notification: CloudEvent):
    print(f"🔔 new notification: {notification.data}", flush=True)
    return ConsumerResult.SUCCESS
```

In the example above, the `on_task_notification` function will be registered as a subscriber to the `task-notifications` topic (based on the method name).
This example shows how to consume raw cloud events, but you can also consume messages as a strongly typed model:

```python
@consumer_app.consume
async def on_task_notification(state_changed_event: StateChangeEvent):
    print(f"🔔 new state changed event: {state_changed_event}")
    return ConsumerResult.SUCCESS
```

### Handling different event types

In the current implementation, each type of event is published to a separate topic.

To bind to multiple event types, you add new methods and name based on the event type:


```python
@consumer_app.consume
async def on_task_notification(state_changed_event: StateChangeEvent):
    print(f"🔔 new task state changed event: {state_changed_event}")
    return ConsumerResult.SUCCESS

@consumer_app.consume
async def on_user_notification(state_changed_event: StateChangeEvent):
    print(f"🔔 new user state changed event: {state_changed_event}")
    return ConsumerResult.SUCCESS

```

### Multiple subscribers to the same event type in a single app (Dapr)

The previous examples all use a common Dapr pubsub component.
That pubsub component doesn't configure the `consumerID` property that determines which Service Bus subscription to use.
In this scenario, Dapr will use the app-id by default (e.g. `subscriber-dapr-simplified`).
This means that you cannot have two separate subscribers for the same event type in the same app using this approach.

> Aside: the reason behind this is that the `consumerID` is set on the pubsub component, whereas the topic name can be set when configuring the subscription in code.
> [This issue](https://github.com/dapr/dapr/issues/814) on GitHub tracks the proposal to allow the `consumerID` to be set when configuring the subscription in code which would add more flexibility.

If you want to have multiple different subscriptions for the same event type in a single app, you can use a separate Dapr pubsub component for each subscription and configure the `consumerID` property on each component.


```python
# This example code assumes additional Dapr pubsub components named "notifications-pubsub-subscriber1" and "notifications-pubsub-subscriber2"
# each with a different consumerID configured

@consumer_app.consume(pubsub_name="notifications-pubsub-subscriber1")
async def on_task_notification1(state_changed_event: StateChangeEvent):
    print(f"🔔 new task state changed event - handler 1: {state_changed_event}")
    return ConsumerResult.SUCCESS

@consumer_app.consume(pubsub_name="notifications-pubsub-subscriber2")
async def on_task_notification2(state_changed_event: StateChangeEvent):
    print(f"🔔 new task state changed event - handler 2: {state_changed_event}")
    return ConsumerResult.SUCCESS
```

## Helper code - Service Bus SDK

### Overview

In the `subscriber-dapr-simplified` folder, you'll find a `consumer_app.py` file under the `PubSub` folder that contains the helper code.
This is an experiment, but the idea is to provide a simple way to consume messages using Dapr pubsub without having to worry about the details of the Dapr API.

The `ConsumerApp` class provides a simple way to register functions as subscribers to topics.
It uses a convention-based approach to determine the topic name name to use.
It also provides a way to customise the topic name and subscriber name if needed.

The code to use this `ConsumerApp` looks very similar to the code for the Dapr helper version:

```python
consumer_app = ConsumerApp()

# We can consume raw cloud events:
@consumer_app.consume
async def on_task_notification(notification: CloudEvent):
    print(f"🔔 new task state changed event: {state_changed_event}")
    return ConsumerResult.SUCCESS
```

In the example above, the `on_task_notification` function will be registered as a subscriber to the `task-notifications` topic (based on the method name).
The handler in this example takes a `CloudEvent`, but can also take a strongly typed model:

```python
# Or we can consume strongly typed events:
@consumer_app.consume
async def on_task_notification(state_changed_event: StateChangeEvent):
    print(f"🔔 new task state changed event: {state_changed_event}")
    return ConsumerResult.SUCCESS
```

### Multiple subscribers to the same event type in a single app (SDK)

The previous examples all use a common Service Bus subscription name across topics.
This means that you cannot have multiple subscribers for the same event type in the same app using this approach.
However, the `consume` method allows you to specify a custom subscription name to use:

```python
@consumer_app.consume(subscription_name="my-custom-subscription")
async def on_task_notification(state_changed_event: StateChangeEvent):
    print(f"🔔 new task state changed event: {state_changed_event}")
    return ConsumerResult.SUCCESS
```
