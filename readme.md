## Manifest template

Use [manifest.template.yaml](./manifest.template.yaml) as a starting point for
a document package. It shows every supported task type (`form`, `copy`,
`image_to_pdf`, `pdf_merge`, and `skip`), including the single-file and
multiple-file forms for `copy` and `image_to_pdf`.

The output folder is the manifest's directory followed by `context.target_date`.
Relative paths for `form.source`, `copy`, and `image_to_pdf` are resolved from
the process current working directory. Relative `pdf_merge.inputs` and
`pdf_merge.output` are instead resolved from the output folder. See the
template comments for absolute paths, environment, context, and task variables.

During `check`, a missing path input (or a `form.filled_pattern` match) is
reported as `[OK-GENERATED]` when an earlier `copy`, `image_to_pdf`, or
`pdf_merge` task in the manifest is expected to produce that path. This follows
manifest order, which is also the order used by `build`; a task's outputs count
only when its own inputs are present or generated earlier in the chain.
Unmatched or ambiguous planned outputs remain missing.

## Building a Windows executable

Build on Windows using the same Python architecture (32-bit or 64-bit) as the
target machine. From the project directory, create and activate a virtual
environment, then install the runtime and packaging dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install PyYAML Pillow PyMuPDF pyinstaller
```

The application computes its root from its own location and uses the
`Formulars` path under that root when resolving manifest variables. In a
frozen build, the root is the directory containing the executable. The
`Formulars` directory and its contents are external runtime data: they are not
included in the build, but the directory must exist beside the executable at
runtime. Place the executable bundle in each document tree alongside that
tree's own `Formulars` directory. Build a console executable:

```powershell
python -m PyInstaller --clean --noconfirm --onefile --console --name bureaucrat `
  --collect-all fitz `
  .\bureaucrat.py
```

The distributable is the single `dist\bureaucrat.exe` file. PyInstaller
bundles the Python runtime and dependencies into the executable and extracts
them to a temporary directory when it runs. Place the required `Formulars`
directory beside the executable; it remains external document-tree data.
Test the executable from a process folder containing the manifest and input
files, so relative manifest paths resolve as expected:

```powershell
& ".\dist\bureaucrat.exe" `
  --manifest .\manifest.yaml --command check
```

Use `--command build` to assemble the package or `--command clean` to remove
generated files. Add `--debug` for diagnostic output. The executable has a
console so that command-line logs and errors remain visible.