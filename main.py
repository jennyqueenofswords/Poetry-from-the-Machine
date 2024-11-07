import streamlit as st # type: ignore
import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import subprocess
import shutil
import atexit
import re

# -----------------------
# Helper Functions
# -----------------------

def sanitize_filename(filename):
    """
    Sanitize filenames by replacing spaces with underscores and removing
    characters that LaTeX might interpret incorrectly.
    """
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    # Remove any characters that are not alphanumeric, underscores, hyphens, or dots
    filename = re.sub(r'[^\w\-_\.]', '', filename)
    return filename

def escape_latex(s):
    """
    Escape LaTeX special characters in a string.
    """
    replacements = {
        '\\': r'\textbackslash{}',
        '{': r'\{',
        '}': r'\}',
        '#': r'\#',
        '$': r'\$',
        '%': r'\%',
        '&': r'\&',
        '_': r'\_',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
    }
    regex = re.compile('|'.join(re.escape(key) for key in replacements.keys()))
    return regex.sub(lambda match: replacements[match.group()], s)

# -----------------------
# Cleanup Function
# -----------------------

def cleanup():
    """
    Remove temporary directories upon application exit to prevent clutter.
    """
    dirs = ['temp_images', 'compiled_images']
    for dir in dirs:
        if os.path.exists(dir):
            shutil.rmtree(dir)

atexit.register(cleanup)

# -----------------------
# Streamlit Application
# -----------------------

st.set_page_config(page_title="Poem Anthology Builder", layout="wide")

st.title("📚 Poem Anthology Builder")

st.markdown("""
Welcome to the **Poem Anthology Builder**! This application helps you compile an anthology from your collection of poems stored as `.txt` files in a local directory. For each poem, you can associate one or more images. The application will generate a beautifully formatted PDF using LaTeX.
""")

# -----------------------
# Step 1: Select Local Directory
# -----------------------

st.header("🔍 Select Poems Directory")

default_dir = os.getcwd()
poems_dir = st.text_input("Enter the path to the directory containing your poems:", default_dir)

EXCLUDED_FILES = ['requirements.txt', 'README.txt', 'anthology_builder.py']  # Add any other files you want to exclude

if st.button("📥 Load Poems"):
    poems_path = Path(poems_dir)
    if poems_path.exists() and poems_path.is_dir():
        # List all .txt files excluding those in EXCLUDED_FILES
        poems = [f for f in poems_path.glob("*.txt") if f.name not in EXCLUDED_FILES]
        if poems:
            st.success(f"✅ Found **{len(poems)}** poem(s) in `{poems_path}`.")
            # Initialize session state
            st.session_state.poems_data = {}
            for poem_path in poems:
                poem_name = poem_path.stem
                with open(poem_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Escape LaTeX special characters in content
                escaped_content = escape_latex(content)
                st.session_state.poems_data[poem_name] = {
                    'content': escaped_content,
                    'images': []
                }
        else:
            st.warning("⚠️ No `.txt` files found in the specified directory (excluding excluded files).")
    else:
        st.error("❌ The provided path is not a valid directory.")

# -----------------------
# Step 2: Display Poems and Upload Images
# -----------------------

if 'poems_data' in st.session_state:
    st.header("🖼️ Associate Images with Poems")
    for poem_name, data in st.session_state.poems_data.items():
        with st.expander(poem_name):
            st.write(f"**Content:**\n\n{data['content']}")
            uploaded_files = st.file_uploader(
                f"Upload image(s) for **{poem_name}**",
                accept_multiple_files=True,
                type=['png', 'jpg', 'jpeg', 'pdf'],
                key=poem_name
            )
            if uploaded_files:
                for uploaded_file in uploaded_files:
                    # Sanitize the uploaded file name
                    sanitized_name = sanitize_filename(uploaded_file.name)
                    # Save images to a temporary directory
                    image_dir = Path("temp_images")
                    image_dir.mkdir(parents=True, exist_ok=True)
                    image_path = image_dir / f"{poem_name}_{sanitized_name}"
                    with open(image_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    st.session_state.poems_data[poem_name]['images'].append(image_path)
                st.success(f"✅ Uploaded **{len(uploaded_files)}** image(s) for `{poem_name}`.")

# -----------------------
# Step 3: Generate LaTeX and Compile PDF
# -----------------------

if 'poems_data' in st.session_state and any(data['images'] for data in st.session_state.poems_data.values()):
    st.header("📄 Generate Anthology PDF")
else:
    st.header("📄 Generate Anthology PDF")
    st.warning("⚠️ Please load poems and associate images before generating the anthology.")

if 'poems_data' in st.session_state:
    if st.button("🖨️ Generate Anthology"):
        with st.spinner("⌛ Generating LaTeX code and compiling PDF..."):
            try:
                # Load Jinja2 template
                env = Environment(loader=FileSystemLoader('templates'))
                template = env.get_template('anthology_template.tex')
            except Exception as e:
                st.error(f"❌ Error loading LaTeX template: {e}")
                st.stop()

            # Prepare data for the template
            template_data = {}
            images_dir = Path("compiled_images")
            images_dir.mkdir(exist_ok=True)
            for poem_name, data in st.session_state.poems_data.items():
                template_data[poem_name] = {
                    'content': data['content'].replace('\n', '\\\\\n'),
                    'images': []
                }
                for image_path in data['images']:
                    # Copy images to images_dir
                    dest_image_path = images_dir / image_path.name
                    shutil.copy(image_path, dest_image_path)
                    # Use relative paths for LaTeX
                    relative_image_path = os.path.relpath(dest_image_path, Path.cwd())
                    # Replace backslashes with forward slashes for LaTeX compatibility
                    relative_image_path = relative_image_path.replace('\\', '/')
                    template_data[poem_name]['images'].append(str(relative_image_path))

            try:
                # Render LaTeX code
                latex_code = template.render(poems=template_data)
            except Exception as e:
                st.error(f"❌ Error rendering LaTeX template: {e}")
                st.stop()

            # Save LaTeX code to a file
            try:
                with open("anthology.tex", "w", encoding='utf-8') as f:
                    f.write(latex_code)
            except Exception as e:
                st.error(f"❌ Error writing LaTeX file: {e}")
                st.stop()

            # Compile LaTeX to PDF
            try:
                # Run pdflatex twice to ensure references are updated
                subprocess.run(
                    ["pdflatex", "anthology.tex"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                subprocess.run(
                    ["pdflatex", "anthology.tex"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                st.success("✅ PDF compiled successfully!")
            except subprocess.CalledProcessError as e:
                error_output = e.stderr.decode()
                stdout_output = e.stdout.decode()
                st.error(f"❌ Error compiling LaTeX to PDF:\n{error_output}")
                st.text("ℹ️ LaTeX Compilation Output:")
                st.text(stdout_output)
                st.stop()

            # Step 4: Provide Downloads
            if os.path.exists("anthology.pdf"):
                with open("anthology.pdf", "rb") as f:
                    pdf_bytes = f.read()
                st.download_button(
                    label="📥 Download PDF",
                    data=pdf_bytes,
                    file_name="anthology.pdf",
                    mime="application/pdf"
                )

            if os.path.exists("anthology.tex"):
                with open("anthology.tex", "rb") as f:
                    tex_bytes = f.read()
                st.download_button(
                    label="📥 Download LaTeX Code",
                    data=tex_bytes,
                    file_name="anthology.tex",
                    mime="text/plain"
                )
