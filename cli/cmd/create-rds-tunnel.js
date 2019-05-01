const AWS = require('aws-sdk/index');
const childProcess = require('child_process');

module.exports = async (argv) => {
  const StackName = argv['stack-name'];
  const TunnelPort = argv.port || 9000;

  if (!StackName) {
    throw new Error('Must pass arg --stack-name');
  }

  const cloudformation = new AWS.CloudFormation({ apiVersion: '2010-05-15' });
  const { Stacks } = await cloudformation.describeStacks({ StackName }).promise();
  const outputs = Stacks[0].Outputs.reduce((acc, Output) => {
    acc[Output.OutputKey] = Output.OutputValue;
    return acc;
  }, {});

  const ec2 = new AWS.EC2({ apiVersion: '2016-11-15' });
  const params = {
    Filters: [
      { Name: 'tag:purpose', Values: ['nat'] },
      { Name: 'tag:aws:cloudformation:stack-name', Values: [StackName] },
    ],
  };
  const res = await ec2.describeInstances(params).promise();
  const { Instances } = res.Reservations[0];
  const rdsHost = outputs.MySQLAddress;
  const rdsPort = outputs.MySQLPort;
  const natIP = Instances[0].PublicIpAddress;

  const socketID = `${StackName}-socket`;
  childProcess.spawn('ssh', [
    '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
    '-M',
    '-S', socketID,
    '-fnNT',
    '-L', `${TunnelPort}:${rdsHost}:${rdsPort}`,
    `ec2-user@${natIP}`,
    '-v',
  ], { stdio: 'ignore', detached: true });

  console.log(`Tunnel to ${rdsHost}:${rdsPort} opened at 127.0.0.1:${TunnelPort}`);
};
