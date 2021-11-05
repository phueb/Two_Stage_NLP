# TrainDSMs

## Background

Research code. Under active development.


## Usage

The user defines multiple jobs (e.g. which DSM to train on which corpus) and submits each job to one of 8 machines owned by the [UIUC Learning & Language Lab](http://learninglanguagelab.org/).
To do so, we use [Ludwig](https://github.com/phueb/Ludwig), a command line interface for communicating the job submission system.
To use `Ludwig`, you must be a member of the lab. 

## DSM Architectures

- W2Vec
- Simple RNN, LSTM
- BabyBERTa (Transformer)
