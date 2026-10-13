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
python -m PyInstaller --clean --noconfirm --onedir --console --name bureaucrat `
  --collect-all fitz `
  .\bureaucrat.py
```

The distributable is `dist\bureaucrat\`. Keep the generated contents together;
the executable depends on files in that directory. Test it from a process
folder containing the manifest and input files, so relative manifest paths
resolve as expected:

```powershell
& "C:\path\to\dist\bureaucrat\bureaucrat.exe" `
  --manifest .\manifest.yaml --command check
```

Use `--command build` to assemble the package or `--command clean` to remove
generated files. Add `--debug` for diagnostic output. The executable has a
console so that command-line logs and errors remain visible.