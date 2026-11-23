"""Optional: copy reports and rejected-record files to S3 when S3_BUCKET is set.

Use an IAM role or a least-privilege user that only has s3:PutObject on this prefix.
Credentials come from the standard AWS environment/role chain, never from the code.
"""

import logging
from pathlib import Path

log = logging.getLogger("orderflow.s3")


def upload_dir(directory: Path, bucket: str, prefix: str) -> int:
    import boto3  # imported lazily so S3 stays optional

    s3 = boto3.client("s3")
    count = 0
    for path in sorted(directory.glob("*.csv")):
        key = f"{prefix}/{path.name}"
        s3.upload_file(str(path), bucket, key, ExtraArgs={"ServerSideEncryption": "AES256"})
        log.info("Uploaded %s to s3://%s/%s", path.name, bucket, key)
        count += 1
    return count
