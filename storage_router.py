import os
import boto3
from botocore.config import Config
from typing import List, Dict, Optional, Any
from supabase import create_client, Client
import logging

logger = logging.getLogger(StorageRouter)

class MultiCloudStorageRouter:
    "
    Manages multi-tier cloud storage:
    - Supabase Storage (1GB free): fast assets, metadata, user uploads
    - Cloudflare R2 (10GB free S3): large archives, backups, data ( egress fee)
    "
    def __init__(self):
        self.supabase: Optional[Client] = None
        self.s3_client: Optional[Any] = None
        self.r2_bucket: str = os.getenv(R2_BUCKET_NAME, agent-storage)
        self._init_supabase()
        self._init_r2()

    def _init_supabase(self):
        sb_url = os.getenv(SUPABASE_URL)
        sb_key = os.getenv(SUPABASE_KEY) or os.getenv(SUPABASE_SERVICE_ROLE_KEY)
        if sb_url and sb_key:
            try:
                self.supabase = create_client(sb_url, sb_key)
                logger.info(Supabase storage client initialized.)
            except Exception as e:
                logger.error(fFailed to initialize Supabase client: {e})

    def _init_r2(self):
        endpoint = os.getenv("S3_ENDPOINT_URL") or os.getenv("STORJ_ENDPOINT_URL", "https://gateway.storjshare.io")
        access_key = os.getenv("S3_ACCESS_KEY_ID") or os.getenv("STORJ_ACCESS_KEY") or os.getenv("R2_ACCESS_KEY_ID")
        secret_key = os.getenv("S3_SECRET_ACCESS_KEY") or os.getenv("STORJ_SECRET_KEY") or os.getenv("R2_SECRET_ACCESS_KEY")
        self.r2_bucket = os.getenv("S3_BUCKET_NAME", "agent-vault")

        if endpoint and access_key and secret_key:
            try:
                self.s3_client = boto3.client(
                    "s3",
                    endpoint_url=endpoint,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    config=Config(signature_version="s3v4")
                )
                logger.info(f"S3 Cloud Storage initialized (Endpoint: {endpoint}, Bucket: {self.r2_bucket})")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}")

    def list_files(self, provider: str = all) -> List[Dict[str, Any]]:
        results = []
        # Check Supabase
        if self.supabase and provider in [all, supabase]:
            try:
                buckets = self.supabase.storage.list_buckets()
                for b in buckets:
                    files = self.supabase.storage.from_(b.name).list()
                    for f in files:
                        results.append({
                            name: f.get(name),
                            size: f.get(metadata, {}).get(size, 0),
                            provider: supabase,
                            bucket: b.name,
                            updated_at: f.get(updated_at)
                        })
            except Exception as e:
                logger.warning(fError listing Supabase storage: {e})

        # Check Cloudflare R2
        if self.s3_client and provider in [all, r2]:
            try:
                response = self.s3_client.list_objects_v2(Bucket=self.r2_bucket)
                for item in response.get(Contents, []):
                    results.append({
                        name: item.get(Key),
                        size: item.get(Size),
                        provider: cloudflare_r2,
                        bucket: self.r2_bucket,
                        updated_at: item.get(LastModified).isoformat() if item.get(LastModified) else None
                    })
            except Exception as e:
                logger.warning(fError listing Cloudflare R2 storage: {e})

        return results

    def upload_file(self, file_bytes: bytes, file_name: str, target: str = auto) -> Dict[str, Any]:
        "
        Routes upload automatically:
        - Files < 5MB -> Supabase Storage
        - Files >= 5MB -> Cloudflare R2
        "
        size = len(file_bytes)
        selected_provider = target
        if selected_provider == auto:
            selected_provider = r2 if (size >= 5 * 1024 * 1024 and self.s3_client) else supabase

        if selected_provider == r2 and self.s3_client:
            self.s3_client.put_object(Bucket=self.r2_bucket, Key=file_name, Body=file_bytes)
            return {provider: cloudflare_r2, bucket: self.r2_bucket, file_name: file_name, size: size}
        elif self.supabase:
            bucket_name = agent-files
            try:
                self.supabase.storage.create_bucket(bucket_name, options={public: True})
            except Exception:
                pass
            self.supabase.storage.from_(bucket_name).upload(file_name, file_bytes, {upsert: true})
            public_url = self.supabase.storage.from_(bucket_name).get_public_url(file_name)
            return {provider: supabase, bucket: bucket_name, file_name: file_name, size: size, url: public_url}
        else:
            # Fallback to local /tmp
            local_path = os.path.join(/tmp, file_name)
            with open(local_path, wb) as f:
                f.write(file_bytes)
            return {provider: local_tmp, file_name: file_name, size: size, path: local_path}

storage_router = MultiCloudStorageRouter()
