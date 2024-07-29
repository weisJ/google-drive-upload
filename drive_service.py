from __future__ import annotations
from dataclasses import dataclass

from mimetypes import guess_type
from pathlib import Path
from typing import Sequence

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

FileId = str


@dataclass(order=True)
class FileInfo:
    path: Path
    id: str
    parent: DirInfo


@dataclass
class DirInfo:
    path: Path
    id: FileId
    parent: DirInfo | None


@dataclass(order=True)
class UploadTarget:
    path: Path
    folder: DirInfo


@dataclass(order=True)
class UploadInfo:
    target: UploadTarget
    existing_info: FileInfo | None


@dataclass
class FolderTree:
    dir: DirInfo | None
    children: dict[str, FolderTree]


SCOPES = [
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]

FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

RETRIES = 5

class DriveService:
    def __init__(self, credentials_json: dict):
        self.service_account_mail = credentials_json["client_email"]
        credentials = service_account.Credentials.from_service_account_info(
            credentials_json, scopes=SCOPES
        )
        self.service = build("drive", "v3", credentials=credentials)

    def list_in_folder(self, folder: DirInfo, query: str) -> list[FileInfo]:
        results = (
            self.service.files()
            .list(
                q=f"""
                    '{folder.id}' in parents
                    {'and' if query else ''}
                    {query}
                    """,
                fields="files(id, name)",
            )
            .execute(num_retries=RETRIES)
        )
        return [
            FileInfo(folder.path / f["name"], f["id"], folder)
            for f in results.get("files", [])
        ]

    def list_files_in_folder(self, folder: DirInfo) -> list[FileInfo]:
        return self.list_in_folder(
            folder=folder,
            query=f"'{self.service_account_mail}' in owners and mimeType != '{FOLDER_MIME_TYPE}'",
        )

    def is_owned_by_service(self, fileOrFolder: FileInfo | DirInfo) -> bool:
        results = (
            self.service.files()
            .get(fileId=fileOrFolder.id, fields="owners")
            .execute(num_retries=RETRIES)
        )
        owners = results.get("owners", [])
        return len(owners) == 1 and owners[0]["emailAddress"] == self.service_account_mail

    def list_folders_in_folder(self, folder: DirInfo) -> list[DirInfo]:
        return [
            DirInfo(f.path, f.id, f.parent)
            for f in self.list_in_folder(
                folder=folder,
                query=f"'{self.service_account_mail}' in owners and mimeType = '{FOLDER_MIME_TYPE}'",
            )
        ]

    def is_folder_empty(self, folder: DirInfo) -> bool:
        entries = self.list_in_folder(folder=folder, query="")
        return len(entries) == 0

    def fetch_remote_folder_tree(self, folder: DirInfo) -> FolderTree:
        def build_tree(folder: DirInfo, current_node: FolderTree) -> None:
            folders = self.list_folders_in_folder(folder)
            for folder in folders:
                last = folder.path.parts[-1]
                if last not in current_node.children:
                    node = FolderTree(dir=folder, children={})
                    current_node.children[last] = node
                    build_tree(folder, node)

        root = FolderTree(dir=folder, children={})
        build_tree(folder, root)
        return root

    def ensure_path(self, path: Path, base: DirInfo) -> DirInfo:
        current = base
        for part in path.parts:
            results = (
                self.service.files()
                .list(
                    q=f"'{current.id}' in parents and name = '{part}'",
                    fields="files(id)",
                )
                .execute(num_retries=RETRIES)
            )
            folders = results.get("files", [])
            if folders:
                current = DirInfo(current.path / part, folders[0]["id"], current)
            else:
                # Create folder
                print(
                    f"Folder {part} of path {path} does not exist in drive. Create it."
                )
                folder = (
                    self.service.files()
                    .create(
                        body={
                            "name": part,
                            "mimeType": FOLDER_MIME_TYPE,
                            "parents": [current.id],
                        },
                        fields="id",
                    )
                    .execute(num_retries=RETRIES)
                )
                fid = folder.get("id")
                if not fid:
                    raise Exception("Could not create folder")
                current = DirInfo(current.path / part, fid, current)

        return current

    def delete(self, file: FileInfo | DirInfo) -> None:
        self.service.files().delete(fileId=file.id).execute(num_retries=RETRIES)

    def batch_delete(self, files: Sequence[FileInfo | DirInfo]) -> None:
        if not files:
            return
        def callback(_requ, _resp, exception):
            if exception:
                print(f"An error occurred: {exception}")

        batch = self.service.new_batch_http_request(callback=callback)
        for file in files:
            print(f"Delete stale file {file.path} ({file.id})")
            batch.add(self.service.files().delete(fileId=file.id))
        batch.execute()
        print(f"    ==> Done deleting {len(files)} files.")

    def upload_file(self, input_folder: Path, upload_info: UploadInfo) -> None:
        file = upload_info.target.path
        folder = upload_info.target.folder
        info = upload_info.existing_info
        mime, _ = guess_type(file)
        if mime is None:
            mime = "*/*"
        media = MediaFileUpload(
            input_folder / file, chunksize=1024 * 1024, mimetype=mime, resumable=True
        )
        if info is None:
            print(f"Upload new file {file.name}")
            request = self.service.files().create(
                body={
                    "name": file.name,
                    "parents": [folder.id],
                },
                media_body=media,
                fields="id",
            )
        else:
            print(f"Update existing file {file.name}")
            request = self.service.files().update(
                fileId=info.id,
                media_body=media,
            )
        response = None
        while response is None:
            status, response = request.next_chunk(num_retries=RETRIES)
            if status:
                print("...Uploaded %d%%." % int(status.progress() * 100))
        print(f"    ==> Upload of {file.name} is complete.")
