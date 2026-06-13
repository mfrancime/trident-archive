# Template Instructions

When creating a new use case in the `02-use-cases` folder you **must** follow the following structure to have your PR merged.

Any use case must have: 
- a descriptive title 
- an overview section focused on what the use case should do including a use case architecture diagram
- the prerequisites to execute the example 
- the use case setup instructions
- the use case execution instructions
- any cleanup instructions

# <Replace me with use case sample title\>

## Overview

Add an overview of the use case that your agent is addressing. In this overview you should include the use case details following this table:

### Use case details
| Information         | Details                                                                                                                             |
|---------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| Use case type       | conversational or event-driven                                                                                                      |
| Agent type          | Single or multi-agent                                                                                                               |
| Use case components | any component being demonstrated in your use case.<br/> Includes: tools, rag, multi-modality, observability, evaluation, and others |
| Use case vertical   | the industry of your use case                                                                                                       |
| Example complexity  | Easy, intermediate or advance                                                                                                       |
| SDK used            | Amazon Bedrock AgentCore SDK, boto3, AWS CDK, AWS SDK for Java, ...                                                                |


### Use case Architecture 

The architecture diagram for your example

### Use case key Features

Any functionality of your use case that you want to highlight

## Prerequisites

Prerequisites to execute your use case in a list format. For instance:
* Python 3.10+
* AWS credentials
* boto3 or Amazon Bedrock AgentCore SDK
* ...

## Use case setup

Instructions on how to set up your use case. For instance start with installing the prerequisite packages and infrastructure

```commandline
pip install -r requirements.txt
sh prerequisites.sh
```

## Execution instructions

Instructions on how to run your example. For instance:

```commandline
python agent.py
```

## Clean up instructions

Instructions to delete any created infrastructure. For instance:

```commandline
sh cleanup.sh
```

## Disclaimer
The examples provided in this repository are for experimental and educational purposes only. They demonstrate concepts and techniques but are not intended for direct use in production environments. Make sure to have Amazon Bedrock Guardrails in place to protect against [prompt injection](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-injection.html).
 