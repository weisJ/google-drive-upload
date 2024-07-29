from __future__ import annotations

import os
import sys
import base64
import json
from pathlib import Path
from itertools import chain

import argparse

from drive_service import (
    DriveService,
    DirInfo,
    UploadTarget,
    UploadInfo,
    FolderTree,
)

def decode_credentials(credentials_base64: str) -> dict:
    return json.loads(base64.b64decode(credentials_base64).decode("utf-8"))

def load_credentials(credentials_arg: str) -> dict:
    if credentials_arg.endswith(".json") and Path(credentials_arg).exists():
        return json.load(open(credentials_arg))
    return decode_credentials(credentials_arg)

def safe_chdir(path: Path | str) -> None:
    try:
        os.chdir(path)
    except Exception as e:
        print(f"::error Failed to change directory to {path}: {e}")
        sys.exit(1)

def get_upload_targets(
    driveService: DriveService,
    input_folder: Path,
    globFilter: str,
    output_folder: DirInfo,
) -> list[UploadTarget]:
    cwd = os.getcwd()
    safe_chdir(input_folder)
    input_files = sorted(f for f in Path("./").rglob(globFilter) if f.is_file())
    safe_chdir(cwd)
    return [
        UploadTarget(
            path=f,
            folder=driveService.ensure_path(f.parent, base=output_folder),
        )
        for f in input_files
    ]

def tree_to_list(tree: FolderTree) -> list[DirInfo]:
    result = [tree.dir] if tree.dir else []
    for child in tree.children.values():
        if child.dir:
            result.append(child.dir)
        result.extend(tree_to_list(child))
    return result

def cleanup_folders(driveService: DriveService, folder: FolderTree) -> None:
    def do_clean(folder: FolderTree) -> None:
        for child in folder.children.values():
            do_clean(child)
        if folder.dir and driveService.is_folder_empty(folder.dir):
            print(f"Delete empty folder {folder.dir.path} ({folder.dir.id})")
            driveService.delete(folder.dir)
            print(f"    ==> Done")

    do_clean(folder)

def main() -> None:
    parser = argparse.ArgumentParser(
        prog=sys.argv[0],
        epilog="This tool is used to upload files to the Kombilösen google drive.",
    )
    parser.add_argument(
        "-i",
        "--input",
        help="Path to the folder to be uploaded",
        nargs=1,
        type=str,
        required=True,
    )
    parser.add_argument(
        "-f",
        "--filter",
        help="Glob pattern to filter files in the input folder",
        nargs=1,
        type=str,
        default="*",
        required=False,
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Path to the folder in the drive to which the files should be uploaded",
        nargs=1,
        type=str,
        required=True,
    )
    parser.add_argument(
        "-t",
        "--target",
        help="Folder id of the drive root folder",
        nargs=1,
        type=str,
        required=True,
    )
    parser.add_argument(
        "-c",
        "--credentials",
        help="Base64 encoded credentials.json",
        nargs=1,
        type=str,
        required=True,
    )
    parser.add_argument(
        "--purge-stale",
        help="Delete stale files (i.e. files which aren't present locally) in the output folder",
        nargs="?",
        type=bool,
        default=False,
        const=True,
    )
    args = parser.parse_args()

    print("==== Arguments ====")
    for arg_name, arg_value in vars(args).items():
        print(f"    {arg_name}: {arg_value}")

    credentials_json = load_credentials(args.credentials[0])
    target_id: str = args.target[0]
    input_folder_path = Path(args.input[0])
    globFilter: str = args.filter[0]
    output_folder_path = Path(args.output[0])

    if not input_folder_path.exists():
        raise FileNotFoundError(f"Input folder {input_folder_path} does not exist")
    if not input_folder_path.is_dir():
        raise NotADirectoryError(f"Input folder {input_folder_path} is not a directory")

    driveService = DriveService(credentials_json)

    base_folder = DirInfo(Path(""), target_id, None)
    output_folder = driveService.ensure_path(output_folder_path, base=base_folder)
    upload_targets = get_upload_targets(driveService, input_folder_path, globFilter, output_folder)

    print("==== Local files ====")
    for input_file in upload_targets:
        print(f"{input_file.path} (to {input_file.folder.id})")

    local_folders_to_consider = {
        t.folder.id: t.folder for t in upload_targets
    }

    # Prevent remote paths to include the path of the output folder
    remote_base = DirInfo(Path(""), output_folder.id, None)
    remote_folder_tree = driveService.fetch_remote_folder_tree(remote_base)
    remote_folders_to_consider = {
        t.id: t for t in tree_to_list(remote_folder_tree)
    }
    folders_to_consider = local_folders_to_consider | remote_folders_to_consider

    print("==== Considering the following folders ====")
    for fid, folder in folders_to_consider.items():
        print(f"{folder.path} ({fid})")

    remote_files = list(
        chain.from_iterable(
            driveService.list_files_in_folder(folder)
            for (_, folder) in folders_to_consider.items()
        )
    )

    print("==== Remote files ====")
    for f in remote_files:
        print(f"{f.path} ({f.id})")

    print("==== Uploading new files ====")
    remote_files_by_path = {f.path: f for f in remote_files}
    files_to_upload = [
        UploadInfo(
            target=f,
            existing_info=remote_files_by_path.get(f.path, None),
        )
        for f in upload_targets
    ]
    for upload_info in files_to_upload:
        driveService.upload_file(input_folder_path, upload_info)

    if args.purge_stale:
        print("==== Removing stale remote files ====")
        input_paths_set = set(f.path for f in upload_targets)
        stale_files = [f for f in remote_files if f.path not in input_paths_set]
        driveService.batch_delete(stale_files)

        print("==== Cleaning up empty folders ====")
        cleanup_folders(driveService, remote_folder_tree)

def main_with_github_reporting():
    try:
        main()
    except Exception as e:
        print(f"::error {e}")
        sys.exit(1)

if __name__ == "__main__":
    main_with_github_reporting()
