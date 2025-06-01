import boto3
import config as cnfg
import os
from datetime import datetime, timezone

class StorageService(object):
    def __init__(self):
        self.s3 = boto3.client(
            service_name = 's3',
            aws_access_key_id = cnfg.S3ACCESS_KEY,
            aws_secret_access_key = cnfg.S3SECRET_KEY,
            endpoint_url = "https://storage.yandexcloud.net"
        )
        self.bucket_name = cnfg.BUCKET_NAME
        self.data_file = "time_table.xlsx"

    def check_and_download_if_updated(self, last_known_update: datetime) -> datetime | None:
        """
        Проверяет дату последнего изменения файла в S3.
        Если файл обновлён — скачивает его и возвращает datetime.
        Иначе — возвращает None.
        """
        try:
            response = self.s3.head_object(Bucket=self.bucket_name, Key=self.data_file)
            s3_last_modified: datetime = response['LastModified'].astimezone(timezone.utc)

            if last_known_update is None or s3_last_modified > last_known_update:
                with open(self.data_file, 'wb') as f:
                    self.s3.download_fileobj(self.bucket_name, self.data_file, f)
                return s3_last_modified
            return None
        except self.s3.exceptions.NoSuchKey:
            print("Файл не найден в S3.")
            return None
        except Exception as e:
            print(f"Ошибка при проверке/загрузке файла: {e}")
            return None