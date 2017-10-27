# aws-operating-hours
AWS charge you for the hours that an EC2 instance or RDS DB instance are running, so for every hour that you can keep your dev/staging sites powered off, the more savings you can make. If you work 40 hours a week and leave the instances powered on, you're paying for 128 hours when they're not in use.

This is where this lambda function comes in: It scans instances for specific tags that describe the operational hours of the machine and shuts down and optionally boots accordingly.

## Setup
The setup I've broken down into four stages: the IAM role, the lambda function, CloudWatch and the tagging.

### IAM
Navigate to the IAM console and create a new lambda role `lambda_describe_start_stop_ec2_rds` with the following as an inline policy:

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "ec2:StartInstances",
                "ec2:StopInstances"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "rds:DescribeDBInstances",
                "rds:ListTagsForResource",
                "rds:StartDBInstance",
                "rds:StopDBInstance"
            ],
            "Resource": "*"
        }
    ]
}
```

This will give your lambda function permission to list EC2 and RDS instances, and start and stop them.

### Lambda
In AWS lambda, create a new function that uses the role created in the previous step, with the runtime as Python 3 and upload the code in the [lambda.py](lambda.py) file.

An environment variable then needs to be added for the region that contains your EC2 and/or RDS instances, e.g. `region: eu-west-2`

The other settings can remain the default.

### CloudWatch
In CloudWatch setup a new scheduled rule that will execute the lambda function every 30 minutes, or whatever frequency you desire. 

### Tagging
There are three tags that are considered in this function `Shutdown`, `Startup`, `StartOnDays`. The EC2 or RDS instances that you would like to power down out of hours need to be tagged so the function can detect them, and what times to initiate these actions. Production servers that do not contain these tags will not be affected by the lambda function, they are simply ignored in the script.

#### Shutdown
*(Required)* This is the time that the instance should be shut down if it is still running, e.g. `3:00` or `19:00`. Note that this has the 24-hour clock format.

#### Startup
*(Optional)* This is the time that the instance should be started up if the instance is stopped, e.g. `7:00` or `14:00`. Note that this has the 24-hour clock format.

#### StartOnDays
*(Optional)* By default the instance will start on any day if the `Startup` tag is present, however you may not wish to start up your instances 7 days a week. This tag allows you to specify the days of the week that the instance should be powered up.

There are three options for the value of the tag:

* A range: `1-5`
* Comma separated days: `1,3,7`
* A single day: `6`

Note that Monday is 1, through to Sunday which is 7. So, to run on all weekdays, simply tag `StartOnDays` with the value `1-5`.

