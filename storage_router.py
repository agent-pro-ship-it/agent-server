import os
import boto3
from botocore.config import Config
from typing import List, Dict, Optional, Any
from supabase import create_client, Client
import logging

logger = logging.getLogger("StorageRouter")

class MultiCloudStorageRouter:
    def __init__(self):
        self.supabase: Optional[Client] = None
        self.s3_client: Optional[Any] = None
        self.r2_bucket: str = os.getenv("S3_BUCKET_NAME", "agent-vault")
        self._init_supabase()
        self._init_s3()

    def _init_supabase(self):
        sb_url = os.getenv("SUPABASE_URL")
        sb_key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if sb_url and sb_key:
            try:
                self.supabase = create_client(sb_url, sb_key)
            except Exception as e:
                logger.error(f"Supabase init error: {e}")

    def _init_s3(self):
        endpoint = os.getenv("S3_ENDPOINT_URL") or os.getenv("STORJ_ENDPOINT_URL", "https://gateway.storjshare.io")
        access_key = os.getenv("S3_ACCESS_KEY_ID") or os.getenv("STORJ_ACCESS_KEY")
        secret_key = os.getenv("S3_SECRET_ACCESS_KEY") or os.getenv("STORJ_SECRET_KEY")

        if endpoint and access_key and secret_key:
            try:
                self.s3_client = boto3.client(
                    "s3",
                    endpoint_url=endpoint,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    config=Config(signature_version="s3v4")
                )
                logger.info(f"S3 client connected to {endpoint}")
            except Exception as e:
                logger.error(f"S3 init error: {e}")

    def list_files(self, provider: str = "all") -> List[Dict[str, Any]]:
        results = []
        if self.supabase and provider in ["all", "supabase"]:
            try:
                buckets = self.supabase.storage.list_buckets()
                for b in buckets:
                    files = self.supabase.storage.from_(b.name).list()
                    for f in files:
                        results.append({
                            "name": f.get("name"),
                            "size": f.get("metadata", {}).get("size", 0),
                            "provider": "supabase",
                            "bucket": b.name,
                            "updated_at": f.get("updated_at")
                        })
            except Exception:
                pass

        if self.s3_client and provider in ["all", "s3", "storj"]:
            try:
                response = self.s3_client.list_objects_v2(Bucket=self.r2_bucket)
                for item in response.get("Contents", []):
                    results.append({
                        "name": item.get("Key"),
                        "size": item.get("Size"),
                        "provider": "storj_s3",
                        "bucket": self.r2_bucket,
                        "updated_at": item.get("LastModified").isoformat() if item.get("LastModified") else None
                    })
            except Exception:
                pass

        return results

    def upload_file(self, file_bytes: bytes, file_name: str, target: str = "auto") -> Dict[str, Any]:
        size = len(file_bytes)
        if self.s3_client:
            try:
                self.s3_client.put_object(Bucket=self.r2_bucket, Key=file_name, Body=file_bytes)
                return {"provider": "storj_s3", "bucket": self.r2_bucket, "file_name": file_name, "size": size}
            except Exception as e:
                logger.error(f"S3 upload error: {e}")

        if self.supabase:
            bucket_name = "agent-files"
            try:
                self.supabase.storage.create_bucket(bucket_name, options={"public": True})
            except Exception:
                pass
            self.supabase.storage.from_(bucket_name).upload(file_name, file_bytes, {"upsert": "true"})
            return {"provider": "supabase", "bucket": bucket_name, "file_name": file_name, "size": size}

        return {"provider": "none", "error": "No storage provider available"}

storage_router = MultiCloudStorageRouter()
