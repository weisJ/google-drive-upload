# Action to upload folders to Google Drive

> [!NOTE]
> This action only works with a [Google Service Account](https://cloud.google.com/iam/docs/service-account-overview).

This is a github action to upload a complete folder including its sub-folders (folder-tree) to Google Drive.
Existing files will be overwritten.

## Inputs

### `input`

| Required | **YES** |
| -------- | ------- |

Path to the folder-tree to be uploaded.

### `filter`

| Required | **NO** |
| -------- | ------ |
| Default  | `*`    |

Filter for files in the input folder-tree are included in the upload process. By default this will match all files i.e. everything will be uploaded.

### `target`

| Required | **YES** |
| -------- | ------- |

The **ID** of the folder in Google Drive to which the files should be uploaded to.

> [!NOTE]
> The Google Service Account needs to have write permissions for this folder.

### `output`

| Required | **NO** |
| -------- | ------ |
| Default  | `./`   |

Destination folder in `target` to which files should be placed when uploading. By default this will just be `target`.

### `credentials`

| Required | **YES** |
| -------- | ------- |

The base-64 encoded `credentials.json` for the Google Drive Service account.

See [here](https://stackoverflow.com/questions/46287267/how-can-i-get-the-file-service-account-json-for-google-translate-api/46290808) on how to obtain the credentials.

### `purgeStale`

| Required | **NO**  |
| -------- | ------- |
| Default  | `false` |

Files which are present in the file-tree `<target>/<output>` which are not present in the `<input>` file-tree
will be deleted. This included directories which become empty through this process.

> [!NOTE]
> This will only delete files owned by the service account used for the upload. It will not touch any other files
> owned someone else.

## Example

The following example workflow first produces some files in the `build` folder and the uploads all of those files which are PDFs
to the `github_artifacts`. Lets assume that `secrets.DRIVE_FOLDER_ID` points to a Google Drive folder called `MyDriveFolder` and `build`
looks like this:

```
build/
├── A/
│   ├── fileA1.pdf
│   ├── fileA2.pdf
│   └── stuffA1.txt
├── B/
│   ├── fileB1.pdf
│   ├── stuffB1.txt
│   └── stuffB2.txt
├── C/
│   └── stuffC.png
├── stuff1.txt
└── file1.pdf
```
Then the resulting file-tree in Google Drive will look like the following (assuming that `MyDriveFolder` starts off empty):
```
MyDriveFolder/
└── github_artifacts/
    ├── A/
    │   ├── fileA1.pdf
    │   └── fileA2.pdf
    ├── B/
    │   └── fileB1.pdf
    └── file1.pdf
```

```yaml
# .github/workflows/main.yml
name: Build and upload
on: [push]

jobs:
  my_job:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Produce files
        run: ...

      - name: Upload to Google Drive
        uses: KarlsruheKombiloesen/google-drive-upload@main
        with:
          input: "build"
          target: ${{ secrets.DRIVE_FOLDER_ID }}
          output: "github_artifacts"
          filter: "*.pdf"
          credentials: ${{ secrets.DRIVE_CREDENTIALS }}
          purgeStale: true
```

If during a later workflow run `build/A/fileB1.pdf` is no longer produced such that the local file-tree now looks like this:
```
build/
├── A/
│   ├── fileA1.pdf
│   ├── fileA2.pdf
│   └── stuffA1.txt
├── B/
│   ├── stuffB1.txt
│   └── stuffB2.txt
├── C/
│   └── stuffC.png
├── stuff1.txt
└── file1.pdf
```
Then the (because `purge-stale` is enabled) the corresponding file in the drive will be deleted as well. Because now `MyDriveFolder/github_artifacts/B` is empty, it will be deleted too.
```
MyDriveFolder/
└── github_artifacts/
    ├── A/
    │   ├── fileA1.pdf
    │   └── fileA2.pdf
    └── file1.pdf
```
