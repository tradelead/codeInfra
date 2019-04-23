from troposphere import Tags, ImportValue, Parameter, Sub, GetAtt, Ref, Join, FindInMap, Base64, Output, Export
from troposphere import Template, AWSObject
from troposphere import ec2, rds, sns, elasticache

t = Template()
t.add_version('2010-09-09')

t.add_mapping('NatRegionMap', {
    "us-east-1": {"AMI": "ami-0ff8a91507f77f867"},
    "us-east-2": {"AMI": "ami-0b59bfac6be064b78"},
    "us-west-1": {"AMI": "ami-a0cfeed8"},
    "us-west-2": {"AMI": "ami-0bdb828fd58c52235"},
    "ca-central-1": {"AMI": "ami-0b18956f"},
    "eu-west-1": {"AMI": "ami-047bb4163c506cd98"},
    "eu-west-2": {"AMI": "ami-f976839e"},
    "eu-west-3": {"AMI": "ami-0ebc281c20e89ba4b"},
    "eu-central-1": {"AMI": "ami-0233214e13e500f77"},
    "ap-southeast-1": {"AMI": "ami-08569b978cc4dfa10"},
    "ap-northeast-2": {"AMI": "ami-0a10b2721688ce9d2"},
    "ap-northeast-1": {"AMI": "ami-06cd52961ce9f0d85"},
    "ap-southeast-2": {"AMI": "ami-09b42976632b27e9b"},
    "ap-south-1": {"AMI": "ami-0912f71e06545ad88"},
    "sa-east-1": {"AMI": "aami-07b14488da8ea02a0"},
    "cn-north-1": {"AMI": "ami-0a4eaf6c4454eda75"},
})

# Parameters

keyPair = t.add_parameter(Parameter('KeyPair', Type='String'))

natInstClass = t.add_parameter(Parameter('NATInstClass', Type='String'))
natSSHCidrAllow = t.add_parameter(Parameter('NATSSHCidrAllow', Type='String'))

redisInstClass = t.add_parameter(Parameter('RedisInstClass', Type='String'))
redisInstNum = t.add_parameter(Parameter('RedisInstNum', Type='Number'))

rdsStorage = t.add_parameter(Parameter('RDSStorage', Type='String'))
rdsInstClass = t.add_parameter(Parameter('RDSInstClass', Type='String'))
rdsMasterUser = t.add_parameter(Parameter('RDSMasterUser', Type='String'))
rdsMasterPass = t.add_parameter(Parameter('RDSMasterPass', Type='String'))

# Vars

region = Ref("AWS::Region")
availZoneA = Join("", [region, 'a'])
availZoneB = Join("", [region, 'b'])
pubSnCidr = '172.31.0.0/20'
snCidr = '172.31.16.0/20'
snCidrB = '172.31.32.0/20'

# Setup VPC + Subnets + Internet Gateway +  NAT Instance (bc micro = free trial)

vpc = t.add_resource(ec2.VPC('VPC', CidrBlock = '172.31.0.0/16'))
intGate = t.add_resource(ec2.InternetGateway('InternetGateway'))
gateToInt = t.add_resource(ec2.VPCGatewayAttachment(
    'GatewayToInternet',
    DependsOn=['VPC', 'InternetGateway'],
    VpcId=vpc.Ref(),
    InternetGatewayId=intGate.Ref(),
))

snPub = t.add_resource(ec2.Subnet(
    'SubnetPublic',
    VpcId = vpc.Ref(),
    AvailabilityZone = availZoneA,
    CidrBlock = pubSnCidr,
))

pubRouteTable = t.add_resource(ec2.RouteTable(
    'PublicRouteTable',
    DependsOn = ['VPC'],
    VpcId = vpc.Ref(),
))

pubRoute = t.add_resource(ec2.Route(
    'PublicRoute',
    DependsOn = ['PublicRouteTable', 'InternetGateway'],
    RouteTableId = pubRouteTable.Ref(),
    GatewayId = intGate.Ref(),
    DestinationCidrBlock = '0.0.0.0/0',
))

pubSubnetRouteTableAssc = t.add_resource(ec2.SubnetRouteTableAssociation(
    'PublicSubnetRouteTableAssociation',
    DependsOn = ['SubnetPublic', 'PublicRouteTable'],
    SubnetId = snPub.Ref(),
    RouteTableId = pubRouteTable.Ref(),
))

sn = t.add_resource(ec2.Subnet(
    'SubnetPrivate',
    VpcId = vpc.Ref(),
    AvailabilityZone = availZoneA,
    CidrBlock = snCidr,
))

routeTable = t.add_resource(ec2.RouteTable(
    'PrivateRouteTable',
    DependsOn = ['VPC'],
    VpcId = vpc.Ref(),
))

subnetRouteTableAssc = t.add_resource(ec2.SubnetRouteTableAssociation(
    'PrivateSubnetRouteTableAssociation',
    DependsOn = ['SubnetPrivate', 'PrivateRouteTable'],
    SubnetId = sn.Ref(),
    RouteTableId = routeTable.Ref(),
))

snB = t.add_resource(ec2.Subnet(
    'SubnetPrivateB',
    VpcId = vpc.Ref(),
    AvailabilityZone = availZoneB,
    CidrBlock = snCidrB,
))

routeTableB = t.add_resource(ec2.RouteTable(
    'PrivateRouteTableB',
    DependsOn = ['VPC'],
    VpcId = vpc.Ref(),
))

subnetRouteTableAsscB = t.add_resource(ec2.SubnetRouteTableAssociation(
    'PrivateSubnetRouteTableAssociationB',
    DependsOn = ['SubnetPrivateB', 'PrivateRouteTableB'],
    SubnetId = snB.Ref(),
    RouteTableId = routeTableB.Ref(),
))

# RDS

rdsSubNetGroup = t.add_resource(rds.DBSubnetGroup(
    'RDSMySQLSubnetGroup',
    DBSubnetGroupDescription = 'MySQL Subnet Group',
    SubnetIds = [sn.Ref(), snB.Ref()],
))

rdsAccessSG = t.add_resource(ec2.SecurityGroup(
    'RDSAccessSecurityGroup', 
    GroupDescription = 'RDS Access SG',
    VpcId = vpc.Ref(),
))

rdsSG = t.add_resource(ec2.SecurityGroup(
    'RDSMySQLSecurityGroup',
    GroupDescription = 'MySQL Security Group',
    VpcId = vpc.Ref(),
    SecurityGroupIngress = [{
        'IpProtocol': 'tcp',
        'FromPort': 3306,
        'ToPort': 3306,
        'SourceSecurityGroupId': rdsAccessSG.GetAtt('GroupId'),
    }],
))

mysql = t.add_resource(rds.DBInstance(
    'RDSMySQL',
    AllocatedStorage = rdsStorage.Ref(),
    DBInstanceClass = rdsInstClass.Ref(),
    DBSubnetGroupName = rdsSubNetGroup.Ref(),
    MasterUsername = rdsMasterUser.Ref(),
    MasterUserPassword = rdsMasterPass.Ref(),
    VPCSecurityGroups = [rdsSG.GetAtt('GroupId')],
    PubliclyAccessible = 'false',
    Engine = 'mysql',
    EngineVersion = '8.0',
    AutoMinorVersionUpgrade = 'true',
    AvailabilityZone = availZoneA,
))

# Setup NAT Instance

natSG = t.add_resource(ec2.SecurityGroup(
    'NatSecurityGroup',
    GroupDescription = 'NAT Security Group',
    DependsOn = 'VPC',
    VpcId = vpc.Ref(),
    SecurityGroupIngress = [
        {
            'IpProtocol': 'tcp',
            'FromPort': 80,
            'ToPort': 80,
            'CidrIp': '172.31.0.0/16',
        },
        {
            'IpProtocol': 'tcp',
            'FromPort': 443,
            'ToPort': 443,
            'CidrIp': '172.31.0.0/16',
        },
        {
            'IpProtocol': 'tcp',
            'FromPort': 22,
            'ToPort': 22,
            'CidrIp': natSSHCidrAllow.Ref(),
        }
    ],
))

nat = t.add_resource(ec2.Instance(
    'NAT',
    DependsOn = ["SubnetPublic", "NatSecurityGroup"],
    InstanceType = natInstClass.Ref(),
    SourceDestCheck = 'false',
    KeyName = keyPair.Ref(),
    ImageId = FindInMap('NatRegionMap', region, 'AMI'),
    NetworkInterfaces = [ec2.NetworkInterfaceProperty(
        GroupSet = [natSG.GetAtt('GroupId'), rdsAccessSG.GetAtt('GroupId')],
        AssociatePublicIpAddress = 'true',
        DeviceIndex = 0,
        DeleteOnTermination = 'true',
        SubnetId = snPub.Ref(),
    )],
    UserData = Base64(Join("", [
        "#!/bin/bash\n", 
        "yum update -y && yum install -y yum-cron && chkconfig yum-cron on\n",
        "echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf\n",
        "sudo iptables -t nat -A POSTROUTING -o eth0 -s 172.31.0.0/16 -j MASQUERADE\n",
        "sudo /etc/init.d/iptables save"
    ]))
))

privRoute = t.add_resource(ec2.Route(
    'PrivateRoute',
    DependsOn = ['PrivateRouteTable', 'NAT'],
    RouteTableId = routeTable.Ref(),
    InstanceId = nat.Ref(),
    DestinationCidrBlock = '0.0.0.0/0',
))

# Redis

redisSGAccess = t.add_resource(ec2.SecurityGroup(
    'RedisAccessSecurityGroup', 
    GroupDescription = 'Redis Access SG',
    VpcId = vpc.Ref(),
))

redisSG = t.add_resource(ec2.SecurityGroup(
    'RedisSecurityGroup', 
    GroupDescription = 'Redis SG',
    VpcId = vpc.Ref(),
    SecurityGroupIngress = [{
        'IpProtocol': 'tcp',
        'FromPort': 6379,
        'ToPort': 6379,
        'SourceSecurityGroupId': redisSGAccess.GetAtt('GroupId'),
    }],
))

redisSubnetGroup = t.add_resource(elasticache.SubnetGroup(
    'RedisSubnetGroup',
    Description = 'Redis Subnet Group',
    SubnetIds = [sn.Ref()],
))

redis = t.add_resource(elasticache.CacheCluster(
    'Redis',
    CacheNodeType = redisInstClass.Ref(),
    VpcSecurityGroupIds = [redisSG.GetAtt('GroupId')],
    PreferredAvailabilityZone = availZoneA,
    CacheSubnetGroupName = redisSubnetGroup.Ref(),
    Engine = 'redis',
    EngineVersion = '5.0.3',
    NumCacheNodes = redisInstNum.Ref(),
))

# Topics

newFilledOrderTopic = t.add_resource(sns.Topic('NewFilledOrderTopic'))
newSuccessfulDepositTopic = t.add_resource(sns.Topic('NewSuccessfulDepositTopic'))
newSuccessfulWithdrawalTopic = t.add_resource(sns.Topic('NewSuccessfulWithdrawalTopic'))
newTraderExchangeTopic = t.add_resource(sns.Topic('NewTraderExchangeTopic'))
removeTraderExchangeTopic = t.add_resource(sns.Topic('RemoveTraderExchangeTopic'))

# Outputs

def createExport(name, value, exportName):
    t.add_output(Output(
        name, 
        Value = value, 
        Export = Export(exportName)
    ))

createExport('Subnet', sn.Ref(), Sub('${AWS::StackName}-SubnetID'))
createExport('RDSAccessSG', rdsAccessSG.GetAtt('GroupId'), Sub('${AWS::StackName}-RDS-Access-SG-ID'))
createExport('MySQLPort', mysql.GetAtt('Endpoint.Port'), Sub('${AWS::StackName}-MySQL-Port'))
createExport('MySQLAddress', mysql.GetAtt('Endpoint.Address'), Sub('${AWS::StackName}-MySQL-Address'))
createExport('RedisAccessSG', redisSGAccess.GetAtt('GroupId'), Sub('${AWS::StackName}-Redis-Access-SG-ID'))
createExport('RedisPort', redis.GetAtt('RedisEndpoint.Port'), Sub('${AWS::StackName}-Redis-Port'))
createExport('RedisAddress', redis.GetAtt('RedisEndpoint.Address'), Sub('${AWS::StackName}-Redis-Address'))
createExport('NewFilledOrderTopic', newFilledOrderTopic.Ref(), Sub('${AWS::StackName}-NewFilledOrderTopicArn'))
createExport('NewSuccessfulDepositTopic', newSuccessfulDepositTopic.Ref(), Sub('${AWS::StackName}-NewSuccessfulDepositTopicArn'))
createExport('NewSuccessfulWithdrawalTopic', newSuccessfulWithdrawalTopic.Ref(), Sub('${AWS::StackName}-NewSuccessfulWithdrawalTopicArn'))
createExport('NewTraderExchangeTopic', newTraderExchangeTopic.Ref(), Sub('${AWS::StackName}-NewTraderExchangeTopicArn'))
createExport('RemoveTraderExchangeTopic', removeTraderExchangeTopic.Ref(), Sub('${AWS::StackName}-RemoveTraderExchangeTopicArn'))

# Save File

with open('template.yml', 'w') as f:
    f.write(t.to_yaml())
