from troposphere import Tags, ImportValue, Parameter, Sub, GetAtt, Ref, Join, FindInMap, Base64, Output, Export
from troposphere import Template, AWSObject
from troposphere import ec2, rds, sns, elasticache, autoscaling, iam, ecs, elasticloadbalancingv2

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

t.add_mapping('ECSRegionMap', {
    "us-east-1": {"AMI": "ami-0bc08634af113cccb"},
    "us-east-2": {"AMI": "ami-00cffcd24cb08edf1"},
    "us-west-1": {"AMI": "ami-05cc68a00d392447a"},
    "us-west-2": {"AMI": "ami-0054160a688deeb6a"},
    "ca-central-1": {"AMI": "ami-039a05a64b90f63ee"},
    "eu-west-1": {"AMI": "ami-09cd8db92c6bf3a84"},
    "eu-west-2": {"AMI": "ami-016a20f0624bae8c5"},
    "eu-west-3": {"AMI": "ami-0b4b8274f0c0d3bac"},
    "eu-central-1": {"AMI": "ami-0ab1db011871746ef"},
    "ap-southeast-1": {"AMI": "ami-0c5b69a05af2f0e23"},
    "ap-northeast-2": {"AMI": "ami-0470f8828abe82a87"},
    "ap-northeast-1": {"AMI": "ami-00f839709b07ffb58"},
    "ap-southeast-2": {"AMI": "ami-011ce3fbe73731dfe"},
    "ap-south-1": {"AMI": "ami-0d143ad35f29ad632"},
    "sa-east-1": {"AMI": "aami-04e333c875fae9d77"},
})

# Parameters

keyPair = t.add_parameter(Parameter('KeyPair', Type='String'))

natInstClass = t.add_parameter(Parameter('NATInstClass', Type='String'))
ecsInstClass = t.add_parameter(Parameter('ECSInstClass', Type='String'))
ecsInstMin = t.add_parameter(Parameter('ECSInstMin', Type='Number'))
ecsInstMax = t.add_parameter(Parameter('ECSInstMax', Type='Number'))

redisInstClass = t.add_parameter(Parameter('RedisInstClass', Type='String'))
redisInstNum = t.add_parameter(Parameter('RedisInstNum', Type='Number'))

rdsStorage = t.add_parameter(Parameter('RDSStorage', Type='String'))
rdsInstClass = t.add_parameter(Parameter('RDSInstClass', Type='String'))
rdsMasterUser = t.add_parameter(Parameter('RDSMasterUser', Type='String'))
rdsMasterPass = t.add_parameter(Parameter('RDSMasterPass', Type='String'))

t.add_parameter(Parameter('CertificateArn', Type='String'))

# Vars

vpcCidr = '172.31.0.0/16'
region = Ref("AWS::Region")
availZoneA = Join("", [region, 'a'])
availZoneB = Join("", [region, 'b'])
pubSnCidr = '172.31.0.0/20'
pubSnBCidr = '172.31.48.0/20'
snCidr = '172.31.16.0/20'
snCidrB = '172.31.32.0/20'

# Setup VPC + Subnets + Internet Gateway +  NAT Instance (bc micro = free trial)

vpc = t.add_resource(ec2.VPC('VPC', CidrBlock = vpcCidr))
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

snPubB = t.add_resource(ec2.Subnet(
    'SubnetPublicB',
    VpcId = vpc.Ref(),
    AvailabilityZone = availZoneB,
    CidrBlock = pubSnBCidr,
))

pubBRouteTable = t.add_resource(ec2.RouteTable(
    'PublicBRouteTable',
    DependsOn = ['VPC'],
    VpcId = vpc.Ref(),
))

pubBRoute = t.add_resource(ec2.Route(
    'PublicBRoute',
    DependsOn = ['PublicBRouteTable', 'InternetGateway'],
    RouteTableId = pubBRouteTable.Ref(),
    GatewayId = intGate.Ref(),
    DestinationCidrBlock = '0.0.0.0/0',
))

pubBSubnetRouteTableAssc = t.add_resource(ec2.SubnetRouteTableAssociation(
    'PublicBSubnetRouteTableAssociation',
    DependsOn = ['SubnetPublicB', 'PublicBRouteTable'],
    SubnetId = snPubB.Ref(),
    RouteTableId = pubBRouteTable.Ref(),
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
    EngineVersion = '5.6',
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
            'CidrIp': vpcCidr,
        },
        {
            'IpProtocol': 'tcp',
            'FromPort': 443,
            'ToPort': 443,
            'CidrIp': vpcCidr,
        }
    ],
))

natIAMRole = t.add_resource(iam.Role(
    'NATRole',
    AssumeRolePolicyDocument = {
        'Version': '2012-10-17',
        'Statement': [{
            'Effect': 'Allow',
            'Principal': {
                'Service': ['ec2.amazonaws.com']
            },
            'Action': ['sts:AssumeRole'],
        }]
    },
    Policies = [iam.Policy(
        PolicyName = 'ec2',
        PolicyDocument = {
            'Version': '2012-10-17',
            'Statement': [{
                'Effect': 'Allow',
                'Action': ['ec2:ModifyInstanceAttribute'],
                'Resource': '*',
            },
            {
                'Effect': 'Allow',
                'Action': ['ec2:CreateRoute', 'ec2:ReplaceRoute'],
                'Resource': Sub('arn:aws:ec2:*:*:route-table/${RouteTable}', { 'RouteTable': routeTable.Ref() }),
            }]
        },
    )],
))

natInstProfile = t.add_resource(iam.InstanceProfile(
    'NATInstProfile',
    Roles = [natIAMRole.Ref()],
))

natLaunchConfiguration = t.add_resource(autoscaling.LaunchConfiguration(
    'NATLaunchConfiguration',
    AssociatePublicIpAddress = 'true',
    EbsOptimized = 'false',
    ImageId = FindInMap('NatRegionMap', region, 'AMI'),
    InstanceType = natInstClass.Ref(),
    KeyName = keyPair.Ref(),
    SecurityGroups = [natSG.GetAtt('GroupId'), rdsAccessSG.GetAtt('GroupId')],
    IamInstanceProfile = natInstProfile.Ref(),
    UserData = Base64(Sub(
        """#!/bin/bash
        yum update -y && yum install -y yum-cron && chkconfig yum-cron on
        echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf
        sudo sysctl -p
        sudo iptables -t nat -A POSTROUTING -o eth0 -s ${VPCCidr} -j MASQUERADE
        sudo /etc/init.d/iptables save
        export AWS_DEFAULT_REGION='${AWS::Region}'
        INSTANCEID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
        /usr/bin/aws ec2 modify-instance-attribute --instance-id $INSTANCEID --no-source-dest-check
        aws --region ${AWS::Region} ec2 replace-route --route-table-id ${RouteTablePrivate} --destination-cidr-block '0.0.0.0/0' --instance-id $INSTANCEID || aws --region ${AWS::Region} ec2 create-route --route-table-id ${RouteTablePrivate} --destination-cidr-block '0.0.0.0/0' --instance-id $INSTANCEID
        """,
        {
            'RouteTablePrivate': routeTable.Ref(),
            'VPCCidr': vpcCidr,
        }
    ))
))

natAutoScalingGroup = t.add_resource(autoscaling.AutoScalingGroup(
    'NATAutoScalingGroup',
    DependsOn = ["SubnetPublic", "NatSecurityGroup"],
    MaxSize = 1,
    MinSize = 1,
    LaunchConfigurationName = natLaunchConfiguration.Ref(),
    VPCZoneIdentifier = [snPub.Ref()],
    Tags = [autoscaling.Tag('purpose', 'nat', 'true')],
))

# Setup ECS Cluster

ecsCluster = t.add_resource(ecs.Cluster('AppServicesCluster'))

ecsSG = t.add_resource(ec2.SecurityGroup(
    'ECSSecurityGroup',
    GroupDescription = 'ECS Security Group',
    DependsOn = 'VPC',
    VpcId = vpc.Ref(),
))

ecsIAMRole = t.add_resource(iam.Role(
    'ECSRole',
    AssumeRolePolicyDocument = {
        'Version': '2012-10-17',
        'Statement': [{
            'Effect': 'Allow',
            'Principal': {
                'Service': ['ec2.amazonaws.com']
            },
            'Action': ['sts:AssumeRole'],
        }]
    },
    ManagedPolicyArns = ['arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role'],
))

ecsInstProfile = t.add_resource(iam.InstanceProfile(
    'ECSInstProfile',
    Roles = [ecsIAMRole.Ref()],
))

ecsLaunchConfiguration = t.add_resource(autoscaling.LaunchConfiguration(
    'ECSLaunchConfiguration',
    AssociatePublicIpAddress = 'true',
    EbsOptimized = 'false',
    ImageId = FindInMap('ECSRegionMap', region, 'AMI'),
    InstanceType = ecsInstClass.Ref(),
    SecurityGroups = [ecsSG.GetAtt('GroupId')],
    IamInstanceProfile = ecsInstProfile.Ref(),
    UserData = Base64(Sub(
        """#!/bin/bash
        yum update -y && yum install -y yum-cron && chkconfig yum-cron on
        sudo bash -c "echo ECS_CLUSTER=${ECSCluster} >> /etc/ecs/ecs.config"
        """,
        {
            'ECSCluster': ecsCluster.Ref(),
        }
    ))
))

ecsAutoScalingGroup = t.add_resource(autoscaling.AutoScalingGroup(
    'ECSAutoScalingGroup',
    DependsOn = ["SubnetPrivate", "ECSSecurityGroup"],
    MaxSize = ecsInstMax.Ref(),
    MinSize = ecsInstMin.Ref(),
    LaunchConfigurationName = ecsLaunchConfiguration.Ref(),
    VPCZoneIdentifier = [sn.Ref()],
    Tags = [autoscaling.Tag('purpose', 'ecsCluster', 'true')],
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

# Load Balancer

loadBalancerSG = t.add_resource(ec2.SecurityGroup(
    'LoadBalancerSecurityGroup', 
    GroupDescription = 'Load Balancer SG',
    VpcId = vpc.Ref(),
    SecurityGroupIngress = [{
        'IpProtocol': 'tcp',
        'FromPort': 80,
        'ToPort': 80,
        'CidrIp': '0.0.0.0/0',
    },
    {
        'IpProtocol': 'tcp',
        'FromPort': 443,
        'ToPort': 443,
        'CidrIp': '0.0.0.0/0',
    }],
))

coreLoadBalancer = t.add_resource(elasticloadbalancingv2.LoadBalancer(
    'CoreLoadBalancer',
    SecurityGroups = [loadBalancerSG.GetAtt('GroupId')],
    Subnets = [snPub.Ref(), snPubB.Ref()],
))

httpsListener = t.add_resource(elasticloadbalancingv2.Listener(
    'HTTPSListener',
    LoadBalancerArn = coreLoadBalancer.Ref(),
    Port = '443',
    Protocol = 'HTTPS',
    DefaultActions = [elasticloadbalancingv2.Action(
        Type = 'fixed-response',
        FixedResponseConfig = elasticloadbalancingv2.FixedResponseConfig(
            StatusCode = '404',
            ContentType = 'text/html',
            MessageBody = 'Not Found',
        ),
    )],
    Certificates = [elasticloadbalancingv2.Certificate(
        CertificateArn = Ref('CertificateArn')
    )],
))

httpListener = t.add_resource(elasticloadbalancingv2.Listener(
    'HTTPListener',
    LoadBalancerArn = coreLoadBalancer.Ref(),
    Port = '80',
    Protocol = 'HTTP',
    DefaultActions = [elasticloadbalancingv2.Action(
        Type = 'redirect',
        RedirectConfig = elasticloadbalancingv2.RedirectConfig(
            Port = '443',
            Protocol = 'HTTPS',
            StatusCode = 'HTTP_301',
        ),
    )],
))

# Outputs

def createExport(name, value, exportName):
    t.add_output(Output(
        name, 
        Value = value, 
        Export = Export(exportName)
    ))

createExport('VPC', vpc.Ref(), Sub('${AWS::StackName}-VPC-ID'))
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
createExport('NATSecurityGroup', natSG.GetAtt('GroupId'), Sub('${AWS::StackName}-NAT-SG-ID'))
createExport('ECSCluster', ecsCluster.Ref(), Sub('${AWS::StackName}-ECS-Cluster'))
createExport('LoadBalancer', coreLoadBalancer.Ref(), Sub('${AWS::StackName}-LoadBalancer'))
createExport('LoadBalancerSG', loadBalancerSG.GetAtt('GroupId'), Sub('${AWS::StackName}-LoadBalancer-SG-ID'))
createExport('ALBWebListener', httpsListener.Ref(), Sub('${AWS::StackName}-ALB-Web-Listener'))

# Save File

with open('template.yml', 'w') as f:
    f.write(t.to_yaml())
