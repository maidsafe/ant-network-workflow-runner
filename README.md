# Network Workflow Runner

A CLI for running Github Actions workflows that launch and manage Autonomi networks.

These workflows are defined in the [sn-testnet-workflows](https://github.com/maidsafe/sn-testnet-workflows) repository. This is a private repository that can only be accessed by being a member of the `maidsafe` organisation.

The workflows use [actions](https://github.com/maidsafe/sn-testnet-control-action), that in turn use
the [testnet-deploy](https://github.com/maidsafe/sn-testnet-deploy) CLI. It is possible to do
everything via `testnet-deploy` directly, but there are several reasons for using this tool:

* Running through workflows gives us traceability and logs that everyone can see.
* The `testnet-deploy` CLI requires configuration and setup. It is best to use it directly for
  development work, when the deployment needs to be extended in some way.
* There are a myriad of options for launching networks, making the CLI cumbersome to use.
* Due to all these options, running the workflows directly is also cumbersome and error prone.
* There are little extensions in the workflows that perform additional steps after deploys.

## Prerequisites

- Python 3.6 or higher
- Github personal access token with permission to run workflows

### Generating a Token

Follow these steps using the Github web UI:

* Click on your profile icon on the top right, then click on `Settings`.
* From the list on the left, click on `Developer settings`.
* Expand the `Personal access tokens` section and click on `Fine-grained tokens`.
* Click on the `Generate new token` button.
* Give the token any name you want.
* Optionally provide a description. It can be useful to say what repository the token relates to and
  what permissions have been applied.
* Use the `Resource owner` drop down to select the `maidsafe` organisation.
* For `Expiration`, a year should be reasonable.
* In the `Repository access` section, click on `Only select repositories` then select the `sn-testnet-workflows`
  repository.
* Under `Permissions`, expand `Repository permissions`, scroll to `Workflows` at the bottom, then
  select `Read and write` from the `Access` drop down.
* Finally, click on the `Generate token` button.

Now keep a copy of your token somewhere.

## Setup

There are a few tools you will want to setup for launching and working with environments.

### The Workflow Runner

This is the tool provided by this repository. Follow the steps below.

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate
```

2. Install the package in development mode:
```bash
pip install -e .
```

3. Provide your personal access token:
```bash
export WORKFLOW_RUNNER_PAT=your_github_token_here
```

Now try using `runner --help` to confirm the runner is available.

### Digital Ocean CLI

The [doctl](https://github.com/digitalocean/doctl) CLI is recommended to help quickly smoke test
environments. Refer to its documentation to configure the required authentication.

If you need access to our account, speak to one of the team.

### Monitoring and ELK Access

For smoke testing and other things, it is necessary to have access to our monitoring and logging
solutions.

Speak to a member of the team to obtain access.

## Providing an Environment for a Test

We will walk through an example that provides a network for a test.

Very often, the test will be related to a PR, so that is the scenario we will consider.

### Launching the Network

The command for launching the network is as follows:
```
runner workflows launch-network --path <inputs-file-path>
```

The inputs file provides the configuration options for the network. To see all the available
options, the `example-inputs` directory has an example for each available workflow. It also
documents each of the options fairly comprehensively, so I will avoid reiterating that here.

Here is a somewhat typical example for launching a network to test a PR:
```
network-id: 21
network-name: DEV-02
environment-type: staging
rewards-address: 0x03B770D9cD32077cC0bF330c13C114a87643B124

description: "Test further adjustments on #2820 for redialing peers to see if this resolves 'not enough quotes' errors" 
related-pr: 2820

branch: req_resp_fix
repo-owner: RolandSherwin
chunk-size: 4194304 # We are currently using 4MB chunks.

# 3 ETH and 100 tokens
initial-gas: "3000000000000000000"
initial-tokens: "100000000000000000000"

client-vars: ANT_LOG=v,libp2p=trace,libp2p-core=trace,libp2p-kad=trace,libp2p-identify=trace,libp2p-relay=trace,libp2p-swarm=trace
interval: 5000
max-archived-log-files: 1
max-log-files: 1

evm-network-type: custom
evm-data-payments-address: 0x7f0842a78f7d4085d975ba91d630d680f91b1295
evm-payment-token-address: 0x4bc1ace0e66170375462cb4e6af42ad4d5ec689c
evm-rpc-url: https://sepolia-rollup.arbitrum.io/rpc
```

This example will launch a development network, but with a staging configuration. This means it will
be the size of a typical staging environment, where size is the number of VMs/nodes. It is also
using the Arbitrum Sepolia infrastructure for EVM payments. The `custom` type is used to explicitly
provide payment and token contract addresses. We are supplying 3 ETH and 100 ANT tokens to the
uploaders that will execute against the network. There is an Ethereum wallet that provides these
funds, whose secret key is in the workflow definition. The uploaders use the `ant` binary to
continually upload files, thus providing some activity for the network we are testing. The
description and related PR are optional, but it is useful to provide these; as will be seen later,
they are used in the Slack post for the environment. Finally, the branch you want to test is
provided by the repo owner and branch name, since it will typically exist on a fork of the main
`autonomi` repository. The binaries from the branch will be built as part of the deployment process.

Save this file to anywhere you like, though I typically use an `inputs` directory at the root of
this repository. That directory is in the `.gitignore` file. You can then run the command as
specified above, pointing to your inputs file.

When the command executes, the runner will return the URL for the workflow run that was dispatched.
We now need to wait for that run to complete. If you wish, the `workflow` subcommand has a `--wait`
argument that will keep the runner in a loop that waits for the run to either complete or fail.
There is also a `#deployment-alerts` channel in our Slack that you can join. A notification will be
fired in here when the workflow completes. I find this useful because it allows me to go and do
something else until I get a notification.

You can see all the workflow runs using `runner workflows ls`. The tool is using a SQLite database
to keep track of things.

Once the deployment is complete, the next step is to perform a smoke test for the environment.

### Smoke Test

A smoke test is necessary because there is no guarantee the feature branch doesn't have issues.

First, run the following command:
```
runner deployments ls
```

The output will be something like this:
```
=============================================================
                  D E P L O Y M E N T S
=============================================================
ID    Name    Deployed             PR#             Smoke Test
----------------------------------------------------------------------
1     DEV-01  2024-12-30 16:00:13  #2577           ✓
  https://github.com/maidsafe/sn-testnet-workflows/actions/runs/12548887014

<other output snipped>

312   DEV-02  2025-03-21 17:21:37  #2764           -
  https://github.com/maidsafe/sn-testnet-workflows/actions/runs/13997330555
```

The most recent deployment will be at the bottom of the list. An optional `--details` flag will show
the full specification.

Use the following command to guide yourself through a little smoke test:
```
runner deployments smoke-test --id 312
```

There will be a series of questions:
```
Smoke test for DEV-02
----------------------------------------
Branch: RolandSherwin/req_resp_fix

? Are all nodes running? (Use arrow keys)
 » Yes
   No
   N/A
```

We will go through each of these questions to demonstrate how to obtain the answer and verify the
deployment. This may seem a tedious exercise, but the reason all of them have been included is
because the deploy can have a source of failure at any of these steps; more questions have been
added as more failure points have been discovered.

There are several places in the test where we could potentially automate the verification. I will
point these out using an `Optimisation:` note. The only reason I haven't done this so far is just
due to being busy.

#### Nodes Running

This can be determined using the workflow run. Use the URL from the deployments list.

Click on the `post-deploy tasks` job, then expand the `network status` section, and scroll right to
the bottom of the log output. Typically you will see something like this (don't worry about the
specific numbers here; your own deploy could be different):
```
-------
Summary
-------
Total peer cache nodes (3x5): 15
Total generic nodes (19x25): 475
Total symmetric private nodes (0x0): 0
Total full cone private nodes (0x0): 0
Total nodes: 491
Running nodes: 488
Stopped nodes: 0
Added nodes: 3
Removed nodes: 0
```

Most of the time, there will be 1 to 3 nodes that have not started correctly. In this example, it is
indicated by the fact that 3 nodes are in an `Added` state. If the `Running nodes:` matches the
total, you can simply answer `Yes`. If not, we perform a manual step to start these nodes.

Use the `Search logs` textbox to locate the 3 nodes with `ADDED` status:
```
DEV-02-node-7:
  antnode1: 0.3.7 RUNNING
  antnode2: 0.3.7 ADDED
```

In this case, `DEV-02-node-7` is the hostname of the VM. You can use `doctl` to quickly obtain the
VM list:
```
doctl compute droplet list --format "ID,Name,Public IPv4,Status,Memory,VCPUs" | grep "DEV-02"
```

Once you have this, SSH to the VM and run `antctl start --service-name antnode2`. Repeat for each of
the nodes not running. After doing so, you can answer `Yes` to this question and move on.

If there were lots of nodes that were not started here, you could answer `No`. Whenever `No` is
used, you will be given an option to abandon the test, and a failure result will be registered. If
lots of nodes failed to start, there is probably something wrong. You will need to abandon this
deploy and investigate with the developer.

**Optimisation**: we could add a `start nodes` step to the job that would use `testnet-deploy` to
start all the nodes. Nodes that have already been started would be skipped. Without further
optimisations, this would add a few minutes on to the deployment, but it would probably be worth it.

#### Bootstrap Cache Files

Next, you will be asked if the bootstrap cache files are accessible:
```
? Are the bootstrap cache files available? (Use arrow keys)
 » Yes
   No
   N/A
```

Using the same workflow run as above, click on the `launch to genesis` job. Expand the `launch
DEV-XX to genesis` section, then scroll down to the bottom of the logs, where you will see an
inventory report. You will see something like this:
```
=====================
Peer Cache Webservers
=====================
DEV-02-peer-cache-node-1: http://165.22.114.235/bootstrap_cache.json
DEV-02-peer-cache-node-2: http://209.38.165.32/bootstrap_cache.json
DEV-02-peer-cache-node-3: http://165.22.124.225/bootstrap_cache.json
```

Each of those URLs should be accessible. You can simply click on them to verify. If they are
available, answer `Yes` and move on. If not, you should abandon the test and try to determine why.

**Optimisation**: it would be possible to automate this step. You could query DO to get the IP
addresses of the peer cache hosts then just use an HTTP request to make sure they are accessible. A
command could be added to the runner for this.

#### Dashboard Receiving Data

```
? Is the main dashboard receiving data? (Use arrow keys)
 » Yes
   No
   N/A
```

The term "main dashboard" refers to a dashboard within Grafana in our monitoring solution.

When you have obtained access to Grafana, open the `ANT Dashboard Default V3` dashboard. Use the
`TestNet Name` drop down to select the `DEV-02` environment. Then on the right-hand side, just above
the `TestNet Name` selector, you will see a time range option. It will probably have the value `Last
3 hours` by default. For the smoke test, change this to `Last 15 minutes`, just to make sure we are
getting data for our current network. If you are seeing the panels populated by data, such as the `#
NODES RUNNING` panel with a non-zero value, you can answer `Yes` and move on.

#### Generic Nodes Running OK

```
? Do nodes on generic hosts have open connections and connected peers? (Use arrow keys)
 » Yes
   No
   N/A
```

This is just a simple indicator that the generic nodes within the deployment are functioning OK.
Using the same dashboard as above, you should see that the `Host Role` selector has the value
`GENERIC_NODE` by default, so we don't need to change it for this test. With `Last 15 minutes` still
selected, check the `Avg. # Open Connections` and `Avg. # Connected Peers Per Node` panels and make
sure they have non-zero values. If there are no connected peers, something is generally wrong. In
that case, you should answer `No` and abandon the test, then report to the developer and try and
figure out what is wrong. Otherwise, answer `Yes` and move on.

#### Peer Cache Nodes Running OK

```
? Do nodes on peer cache hosts have open connections and connected peers? (Use arrow keys)
 » Yes
   No
   N/A
```

This is the same as the test above, except this time you should use the `Host Role` selector to
select `PEER_CACHE_NODE`. Again, inspect the panels to make sure there are connected peers, and
answer appropriately. If there are not, again there is some kind of problem that needs investigated.

#### Symmetric NAT Private Nodes Running OK

```
? Do symmetric NAT private nodes have open connections and connected peers? (Use arrow keys)
 » Yes
   No
   N/A
```

This time you should select `NAT_RANDOMIZED_NODE` in the `Host Role` selector. Again, you want to
observe connected peers.

Important note: there are some tests where we want to launch an environment without any private
nodes. In this case, you would see 0 connected peers, but you should answer `N/A`, because private
nodes do not apply.

#### Full Cone NAT Private Nodes Running OK

```
? Do full cone NAT private nodes have open connections and connected peers? (Use arrow keys)
 » Yes
   No
   N/A
```

This time you should select `NAT_FULL_CONE_NODE` in the `Host Role` selector. If relevant, again you
want to observe connected peers. If not, use `N/A`.

#### Logs in ELK

```
? Is ELK receiving logs? (Use arrow keys)
 » Yes
   No
   N/A
```

We want to quickly make sure logs for the environment are being forwarded to ELK. When you access
ELK, in the top left, just to the left of the `Search` textbox, there is a little `Saved Queries`
drop down. You should see a saved query for your dev environment. Click on it, and it will apply a
filter that gets the last 15 minutes of logs. You want to see a non-zero value in the `ANT -
ANTNODES - # Log Entries V1` panel. If there are an excessive number of logs, e.g., 500,000 or more,
you may want to flag this, but not necessarily fail the smoke test.

#### Version Numbers for `antnode` and `antctl`

The next two questions will verify that the correct versions of these binaries have been used.

```
? Is `antctl` on the correct version? (Use arrow keys)
 » Yes
   No
   N/A

? Is `antnode` on the correct version? (Use arrow keys)
 » Yes
   No
   N/A
```

There is a little script included in the repository that can perform this check for you:
```
./resources/verify-node-versions.sh "DEV-02" "v0.12.0" "v0.3.7" "req_resp_fix"
```

Vary these argument values as appropriate to your environment. If you are using a versioned build,
the branch name will be something like `stable`, or `rc-*`. In the RC case, the version numbers will
also have RC-based suffixes, e.g., `-rc.1`. It may seem silly to verify these, but it is definitely
possible that you could have specified incorrect values for the workflow inputs. It's happened to me
many times.

**Optimisation**: we could automate this by providing a Python implementation of the script as a
command in the runner tool.

#### Reserved IPs

```
? Are the correct reserved IPs allocated? (Use arrow keys)
 » Yes
   No
   N/A
```

This question only applies to the `STG-01` and `STG-02` environments. In this case, you can use the
Digital Ocean GUI to verify: go to `MANAGE` -> `Networking` -> `Reserved IPs`. You should then see 3
IPs allocated to either of those environments. If you're not using a staging environment, use `N/A`.

#### Verifying Uploaders

The next few questions relate to the uploaders.

```
? Is the uploader dashboard receiving data? (Use arrow keys)
 » Yes
   No
   N/A

? Do uploader wallets have funds? (Use arrow keys)
 » Yes
   No
   N/A
```

Both these questions can be answered by accessing the `ANT Uploaders V1`. As with the main
dashboard, use the `TestNet Name` selector to select your environment and change the time period to
`Last 15 minutes`. You should see the panels populated with some data. If you see this, you can
answer `Yes` to the first question. The first panel can provide the answer to the second question.
The values of `Last Gas Balance` and `Last Token Balance` should roughly correspond to the funding
values provided in the workflow for launching the network. If uploads have been running
successfully, a little bit of the funds will have been used.

```
? Is `ant` on the correct version? (Use arrow keys)
 » Yes
   No
   N/A
```

There is another little script that can verify this:
```
./resources/verify-ant-version.sh "DEV-02" "v0.3.8" "req_resp_fix"
```

It will check all uploaders have the correct version of `ant`.

```
? Do the uploaders have no errors? (Use arrow keys)
 » Yes
   No
   N/A
```

Another helper script can assist with this:
```
./get-uploader-logs.sh "DEV-02" 1
```

This just uses SSH to run the `journalctl` command and get you the logs. The integer argument is to
indicate how many uploaders are running per VM. Vary this as required. Since the smoke test
generally takes place not too long after the environment has been launched, there won't be that many
uploads yet. So you can eyeball the logs to check there are no errors so far. If there are errors,
you may want to fail the test and investigate. Sometimes there could be errors that are expected
that are not related to the branch being tested, and those would be acceptable.

**Optimisation**: the checks using the scripts could be subsumed as commands within the runner.

### Post the Environment to Slack

With the test concluded, whether it passed or failed, there is now an opportunity to post it to
Slack. In most cases you will want to do this, because either you will most likely want to
investigate and discuss the failure, or you will want to indicate to the owner of the PR that the
environment is ready and that the test is running. The post can then serve to document any results
or discuss them. Very often, changes will need to be made to the PR, and that will be discussed
within the thread.

To post the environment details to Slack:
```
runner deployments post --id 312
```
