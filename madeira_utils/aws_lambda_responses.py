import json


########################################################################
# Convenience functions for generation of AWS Lambda Function responses
# consumed by AWS API Gateway
#########################################################################

def get_bad_request_response(error):
    return get_json_response({'error': error}, status_code=400)


def get_json_response(data, status_code=200):
    return dict(
        statusCode=status_code, headers={"Content-Type": "application/json"},
        body=json.dumps(data)
    )
