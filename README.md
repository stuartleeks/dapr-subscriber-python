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
- `subscriber-sdk-simplified` contains the code for the simplified subscriber code using helper code to simplify the Service Bus SDK usage. See the [README.md](src/subscriber-sdk-simplified/README.md) in the folder for more details

## Running locally

If you want to run the code locally, you can also do that. You may want to scale the deployments in the kubernetes cluster to 0 to avoid competing for messages to process 🙂.


To run the code:
- run `just run-subscriber-sdk-direct` to run the subscriber that uses the Service Bus SDK directly
- run `just run-subscriber-sdk-simplified` to run the subscriber that uses the helper code with the Service Bus SDK
- run `just run-publisher` to run the publisher that sends messages to the `task-created` topic. Note that you can use `just run-publisher user-created` to send a message to the `user-created` topic instead, or `just run-publisher task-created 5` to send 5 messages to the `task-created` topic.

