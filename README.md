# python-service-bus-subscribers

This repo is a sample showing how to consume messages from Azure Service Bus using Python. Additionally, it includes an exploration of ways to abstract away large parts of the considerations to simplify the developer experience for consuming messages using a combination of helper code and conventions. 


## Deploying the sample

To deploy the sample:
- open the folder using Visual Studio Code and the Dev Containers extension (this will build a containerised development environment with all the dependencies installed)
- in VS Code terminal, run `az login` to sign in to your Azure account
- copy the `sample.env` file to `.env` and update the values
- run `just deploy` and grab a coffee ☕. This will deploy a container registry, kubernetes cluster, deploy services etc. 

## Repo contents

Within the repo, you'll find:
- `src` folder containing the sample code
- `infra` folder containing Bicep to deploy the sample to Azure
- `scripts` folder containing helper scripts to configure/deploy the sample

Under `src` there are several folders:
- `publisher` contains the code for the publisher that sends messages to Service Bus
- `subscriber-sdk-direct` contains the code for the subscriber that directly uses the Service Bus SDK
- `subscriber-sdk-simplified` contains the code for the simplified subscriber code using helper code to simplify the Service Bus SDK usage

## Running locally

If you want to run the code locally, you can also do that. You may want to scale the deployments in the kubernetes cluster to 0 to avoid competing for messages to process 🙂.


To run the code:
- run `just run-subscriber-sdk-direct` to run the subscriber that uses the Service Bus SDK directly
- run `just run-subscriber-sdk-simplified` to run the subscriber that uses the helper code with the Service Bus SDK
- run `just run-publisher` to run the publisher that sends messages to the `task-created` topic. Note that you can use `just run-publisher user-created` to send a message to the `user-created` topic instead, or `just run-publisher task-created 5` to send 5 messages to the `task-created` topic.

## Helper code

### Overview

In the `subscriber-sdk-simplified` folder, you'll find a `consumer_app.py` file under the `PubSub` folder that contains the helper code.
This is an experiment, but the idea is to provide a simple way to consume messages using the Service Bus SDK without having to worry about the details of the SDK.

The `ConsumerApp` class provides a simple way to register functions as subscribers to topics.
It uses a convention-based approach to determine the topic name name to use.
It also provides a way to customise the topic name and subscriber name if needed.

The `ConsumerApp` class provides a `consume` decorator that can be used to register a function as a subscriber.
This can be used to register a function as a subscriber to a topic:

```python
consumer_app = ConsumerApp()

# We can consume raw cloud events:
@consumer_app.consume
async def on_task_created(notification: CloudEvent):
    print(f"🔔 new task created event: {state_changed_event}")
    return ConsumerResult.SUCCESS
```

In the example above, the `on_task_created` function will be registered as a subscriber to the `task-created` topic (based on the method name).
The handler in this example takes a `CloudEvent`, but can also take a strongly typed model:

```python
# Or we can consume strongly typed events:
@consumer_app.consume
async def on_task_created(state_changed_event: StateChangeEvent):
    print(f"🔔 new task created event: {state_changed_event}")
    return ConsumerResult.SUCCESS
```

### Multiple subscribers to the same event type in a single app (SDK)

The previous examples all use a common Service Bus subscription name across topics.
This means that you cannot have multiple subscribers for the same event type in the same app using this approach.
However, the `consume` method allows you to specify a custom subscription name to use:

```python
@consumer_app.consume(topic_name="task-created", subscription_name="my-custom-subscription")
async def handle_notifications(state_changed_event: StateChangeEvent):
    print(f"🔔 new task created event: {state_changed_event}")
    return ConsumerResult.SUCCESS
```
