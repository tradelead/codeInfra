const AWS = require('aws-sdk/index');
const util = require('util');
const exec = util.promisify(require('child_process').exec);

module.exports = async (argv) => {
  const StackName = argv['stack-name'];

  if (!StackName) {
    throw new Error('Must pass arg --stack-name');
  }

  const ec2 = new AWS.EC2({ apiVersion: '2016-11-15' });
  const params = {
    Filters: [
      { Name: 'tag:purpose', Values: ['nat'] },
      { Name: 'tag:aws:cloudformation:stack-name', Values: [StackName] },
    ],
  };
  const res = await ec2.describeInstances(params).promise();
  const { Instances } = res.Reservations[0];
  const natIP = Instances[0].PublicIpAddress;

  const socketID = `${StackName}-socket`;
  const cmd = `ssh -S ${socketID} -O exit ec2-user@${natIP}`;
  console.log(cmd);
  const { stdout, stderr } = await exec(cmd);
  console.log(stdout);

  if (stderr) {
    console.error(`error: ${stderr}`);
    return;
  }

  console.log(`Closed Tunnel: ${socketID}`);
};
