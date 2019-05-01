const AWS = require('aws-sdk/index');
const https = require('https');
const expireOldSSHRules = require('./util/expireOldSSHRules');

function getIP() {
  return new Promise((resolve, reject) => {
    https.get('https://api.ipify.org/', (res) => {
      res.on('data', (d) => {
        resolve(d.toString());
      });
    }).on('error', e => reject(e));
  });
}

module.exports = async (argv) => {
  const StackName = argv['stack-name'];

  if (!StackName) {
    throw new Error('Must pass arg --stack-name');
  }

  const cloudformation = new AWS.CloudFormation({ apiVersion: '2010-05-15' });
  const { Stacks } = await cloudformation.describeStacks({ StackName }).promise();
  const outputs = Stacks[0].Outputs.reduce((acc, Output) => {
    acc[Output.OutputKey] = Output.OutputValue;
    return acc;
  }, {});

  const natSGID = outputs.NATSecurityGroup;

  const ip = await getIP();

  // Deny IP for SSH
  try {
    const ec2 = new AWS.EC2({ apiVersion: '2016-11-15' });
    const revokeParams = {
      CidrIp: `${ip}/32`,
      FromPort: 22,
      ToPort: 22,
      GroupId: natSGID,
      IpProtocol: 'tcp',
    };
    await ec2.revokeSecurityGroupIngress(revokeParams).promise();
    console.log(`${ip} Denied SSH Access.`);
  } catch (e) {
    if (e.name !== 'InvalidPermission.NotFound') {
      throw e;
    }

    console.log(`Hmm... ${ip} didn't exist in security group. You might have already deleted it or it expired.`);
  }

  // Expire Old Rules
  await expireOldSSHRules(natSGID);
};
