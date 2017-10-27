import boto3, os
from datetime import datetime


def lambda_handler(event, context):
    process_ec2()
    process_rds()


def process_ec2():
    # get ec2 client and return instances that are tagged correctly
    client = boto3.client('ec2', region_name=os.environ['region'])
    response = client.describe_instances(
        Filters=[
            {
                'Name': 'tag-key',
                'Values': [
                    'Shutdown',
                    'Startup',
                ]
            }
        ]
    )

    instance_ids_to_stop = []
    instance_ids_to_start = []

    for reservation in response['Reservations']:
        # loop through all instances with the tags
        for instance in reservation['Instances']:
            # set default for optional tags
            startup_time_str = None
            start_on_days = None

            # obtain the approrpiate values from the tags
            for tag in instance['Tags']:
                if tag['Key'] == 'Shutdown':
                    shutdown_time_str = tag['Value']
                elif tag['Key'] == 'Startup':
                    startup_time_str = tag['Value']
                elif tag['Key'] == 'StartOnDays':
                    start_on_days = tag['Value']

            # if the instance is running and shouldn't be
            if should_stop_instance(state=instance['State']['Name'], 
                                    shutdown_time_str=shutdown_time_str):
                # instance should be shutdown
                instance_ids_to_stop.append(instance['InstanceId'])

            # else is the instance is stopped and shouldn't be?
            elif should_start_instance(state=instance['State']['Name'], 
                                       startup_time_str=startup_time_str, 
                                       shutdown_time_str=shutdown_time_str,
                                       start_on_days=start_on_days):
                # instance should be started
                instance_ids_to_start.append(instance['InstanceId'])


    # start the instances that should be running
    start_instances(client=client, instance_ids=instance_ids_to_start)
    # shut down the instances that shouldn't be running
    stop_instances(client=client, instance_ids=instance_ids_to_stop)


def process_rds():
    # get client and return all rds db instances
    client = boto3.client('rds', region_name=os.environ['region'])
    response = client.describe_db_instances()

    dbinstance_ids_to_stop = []
    dbinstance_ids_to_start = []
    
    # loop through all db instances
    for dbinstance in response['DBInstances']:
        # rds doesn't return the tags in describe instances
        # so need to get the db instance tags
        tag_response = client.list_tags_for_resource(
            ResourceName=dbinstance['DBInstanceArn'],
        )

        # set defaults
        startup_time_str = None
        start_on_days = None
        shutdown_time_str = None

        # obtain the approrpiate values from the tags
        for tag in tag_response['TagList']:
            if tag['Key'] == 'Shutdown':
                shutdown_time_str = tag['Value']
            elif tag['Key'] == 'Startup':
                startup_time_str = tag['Value']
            elif tag['Key'] == 'StartOnDays':
                start_on_days = tag['Value']

        if shutdown_time_str is None:
            # no shut down time specified, so
            # skip this db instance
            continue

        # if the instance is running and shouldn't be
        if should_stop_instance(state=dbinstance['DBInstanceStatus'], 
                                shutdown_time_str=shutdown_time_str):
            # instance should be shutdown
            dbinstance_ids_to_stop.append(dbinstance['DBInstanceIdentifier'])

        # else is the instance is stopped and shouldn't be?
        elif should_start_instance(state=dbinstance['DBInstanceStatus'], 
                                   startup_time_str=startup_time_str, 
                                   shutdown_time_str=shutdown_time_str,
                                   start_on_days=start_on_days):
            # instance should be started
            dbinstance_ids_to_start.append(dbinstance['DBInstanceIdentifier'])


    # start the db instances that should be running
    start_dbinstances(client=client, dbinstance_ids=dbinstance_ids_to_start)
    # shut down the db instances that shouldn't be running
    stop_dbinstances(client=client, dbinstance_ids=dbinstance_ids_to_stop)


def should_stop_instance(state, shutdown_time_str):
    shutdown_time = datetime.strptime(shutdown_time_str, '%H:%M').time()
    return state in ('running', 'available') and shutdown_time <= datetime.now().time()


def should_start_instance(state, startup_time_str, shutdown_time_str, start_on_days):
    if state == 'stopped' and startup_time_str and start_today(start_on_days=start_on_days):    
        startup_time = datetime.strptime(startup_time_str, '%H:%M').time()
        shutdown_time = datetime.strptime(shutdown_time_str, '%H:%M').time()

        if startup_time <= datetime.now().time() < shutdown_time:
            return True

    return False


def start_today(start_on_days):
    """
    Start on days takes two different forms, integer days separated
    by commas, e.g. 1,4,5 or ranges, e.g. 1-5.

    Days of the week start are 1 for Monday through to 7 for Sunday.
    """
    # if not specified default to true
    if not start_on_days:
        return True

    if ',' in start_on_days:
        # comma separated list
        days = list(map(int, start_on_days.split(',')))

    elif '-' in start_on_days:
        # range
        days = list(map(int, start_on_days.split('-')))

    else:
        # single day
        days = [int(start_on_days)]

    # python uses weekdays from 0-6, i think 1-7 feels
    # more natural, so translate
    if (datetime.now().weekday() + 1) in days:
        return True

    return False


def start_instances(client, instance_ids):
    if instance_ids:
        response = client.start_instances(
            InstanceIds=instance_ids,
        )

        for instance in response['StartingInstances']:
            print_state_change_ec2(instance=instance)


def stop_instances(client, instance_ids):
    if instance_ids:
        response = client.stop_instances(
            InstanceIds=instance_ids,
        )

        for instance in response['StoppingInstances']:
            print_state_change_ec2(instance=instance)


def print_state_change_ec2(instance):
    print ('Changing: %(instance_id)s from %(prev_state)s -> %(cur_state)s' % {
        'instance_id': instance['InstanceId'],
        'prev_state': instance['PreviousState']['Name'],
        'cur_state': instance['CurrentState']['Name'],
    })


def start_dbinstances(client, dbinstance_ids):
    for dbinstance_id in dbinstance_ids:
        response = client.start_db_instance(
            DBInstanceIdentifier=dbinstance_id,
        )

        print('Starting RDS: %s' % response['DBInstance']['DBInstanceArn'])


def stop_dbinstances(client, dbinstance_ids):
    for dbinstance_id in dbinstance_ids:
        response = client.stop_db_instance(
            DBInstanceIdentifier=dbinstance_id,
        )

        print('Shutting down RDS: %s' % response['DBInstance']['DBInstanceArn'])


if __name__ == '__main__':
    main()
