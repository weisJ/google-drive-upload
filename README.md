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

## Setup
This section explains how to setup a Google Service Account and how to configure it for use with this action.

### Google Service Account (GSA)
First of all you will need a **Google Service Account** for your project. Service accounts are just specific Google account types that are used by services instead of people.
To make one go to [*Service Accounts*](https://console.cloud.google.com/apis/credentials) in the *IAM and administration* section of the **Google Cloud Plattform** dashboard and create a new project or choose the one you are already using for your current shenanigans.
Click on create new service account and continue with the process. At the end you will get the option to generate a key, **we need this key so store it safely**. It's a json file with the following structure:
```json
{
  "type": "...",
  "project_id": "...",
  "private_key_id": "...",
  "private_key": "...",
  "client_email": "...",
  "client_id": "...",
  "auth_uri": "...",
  "token_uri": "...",
  "auth_provider_x509_cert_url": "...",
  "client_x509_cert_url": "...",
  "universe_domain": "..."
}
```

### Share Drive folder with the GSA
Go to your **Google Drive** and find the folder you want your files to be uploaded to and share it with the GSA. You can find your service account email address in the `client_email` property of your GSA credentials.
While you are here, take a note of **the folder's ID**, the long set of characters after the last `/` in your address bar if you have the folder opened in your browser.
This is the value you want to pass to the `target` parameter of this action.

### Store credentials as GitHub secrets
This action needs your GSA credentials to properly authenticate with Google. To avoid leaking these credentials it is highly advisable to store them as repository secrets.
Go to the **Secrets** section of your repo and add a new secret for your credentials. As per GitHub's recommendation, we will store any complex data (like the JSON credentials) as a base64 encoded string.
You can encode jour `.json` file easily into a new `.txt` file using any bash terminal (just don't forget to change the placeholders with the real name of your credentials file and and the desired output):
```bash
$ base64 CREDENTIALS_FILENAME.json > ENCODED_CREDENTIALS_FILENAME.txt
```
The contents of the newly generated `.txt` file is what we have to procure as a value for our secret.

> [!Important]
> This action assumes that the credentials are stored as a base64 encoded string. If that's not the case, the action will **fail**.

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
