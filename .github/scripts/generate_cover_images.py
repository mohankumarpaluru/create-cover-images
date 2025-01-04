#!/usr/bin/env python3

"""
Script to generate open graph images for markdown files and update markdown content with image url
"""

import base64
import os
import random
import re
import tempfile
import textwrap
from datetime import datetime
from pathlib import Path

from ruamel import yaml as ryaml

from PIL import Image, ImageDraw, ImageFont
from github import Github, InputGitTreeElement

# Helper constants
COMMIT_MSG = "Updating Covers and Deploying"
BRANCH = "main"
COVERS_DIR = "public/assets/blog/covers/"
GITHUB_USERNAME = "mohankumarpaluru"
COVER_REPO = "blog-cover-generator"
NOTES_REPO = "notes"
PUBLISH_TRIGGER_FILE = '.github/trigger_files/publish.txt'
JOURNAL_TRIGGER_FILE = '.github/trigger_files/journal.txt'


def clean_text_for_filename(text):
    """Clean text to generate filename

    Args:
        text (str): Text to clean

    Returns:
        str: Cleaned text for filename
    """
    cleaned_text = text.replace(' ', '_').replace('-', ' ')
    cleaned_text = re.sub(r'[^a-zA-Z0-9]', '', cleaned_text)
    return cleaned_text.lower()


def update_properties(file_path=None, file_content=None):
    """Update markdown properties with generated image

    Args:
        content (str): Markdown content
        file_path (Path): File path

    Returns:
        tuple[str, str, str]: Title, image filename, updated content
    """
    file_path = Path(file_path)
    if not file_content and file_path.is_file():
        with file_path.open('r', encoding='utf-8') as md_file:
            file_content = md_file.read()
    current_date = datetime.now()
    formatted_date = current_date.strftime("%Y-%m-%d")
    match = re.search(r'^\s*---(.*?)---', file_content, re.DOTALL)
    cdn_url_prefix = "https://cdn.jsdelivr.net/gh/" \
                     f"{GITHUB_USERNAME}/{COVER_REPO}@{BRANCH}/{COVERS_DIR}"
    yaml=ryaml.YAML(typ='safe')
    yaml.default_flow_style = False
    if match:
        # print('Properties Identified')
        properties = yaml.load(match.group(1))
        note_title = properties.get('title', None)
        if not note_title:
            note_title = file_path.stem
            properties['title'] = note_title
        note_date =  properties.get('date', None)
        dont_up_date =  properties.get('dupdate', None)

        og_image = properties.get('ogImage', {})
        og_image_url = og_image.get('url')

        if og_image_url and (note_date == formatted_date):
            return False, False, False

        if og_image_url:
            png_file_name = False
        else:
            png_file_name = f'{clean_text_for_filename(note_title)}.png'
            properties.setdefault('ogImage', {'url': f'{cdn_url_prefix}{png_file_name}'})
        if not dont_up_date:
            properties['date'] = formatted_date
        props_stream = ryaml.compat.StringIO()
        yaml.dump(properties, props_stream)
        props = props_stream.getvalue()
        file_content = re.sub(pattern=r'^\s*---(.*?)---', repl='---\n' + props + '---',
                            string=file_content, count=1, flags= re.DOTALL)

    else:
        # print("Couldn't identify properties")
        note_title = file_path.stem
        png_file_name = f'{clean_text_for_filename(note_title)}.png'
        properties = {
            'title': note_title,
            'ogImage': {'url': f'{cdn_url_prefix}{png_file_name}'},
            'date': formatted_date
        }
        props_stream = ryaml.compat.StringIO()
        yaml.dump(properties, props_stream)
        props = props_stream.getvalue()
        file_content = '---\n' + props + '---\n\n' + file_content

    return note_title, png_file_name, file_content


def create_image(input_text, output_file, font_size=70, max_line_length=32):
    """Generate image with centered text

    Args:
        text (str): Text to render
        output_file (Path): Output image file path
        font_size (int, optional): Font size. Defaults to 70.
        max_line_length (int, optional): Max characters in line. Defaults to 32.
    """
    rand_img_no = random.randint(1, 100)

    if rand_img_no % 2 == 0:
        omit_start_width, region_width, region_height, fill_color = 0, 1450, 1000, "#D3D3D3"
        background_image_path = Path('__file__').parent / ".github" / "scripts" / "cover-black-red.png"
        font_path = Path('__file__').parent / ".github" / "scripts" / "Chalkduster.ttf"
    else:
        omit_start_width, region_width, region_height, fill_color = 500, 2000, 1000, "#36454F"
        background_image_path = Path('__file__').parent / ".github" / "scripts" / "cover-white-cyan.png"
        font_path = Path('__file__').parent / ".github" / "scripts" / "Helvetica-Neue-LT.ttf"
        font_size += 30

    image = Image.open(background_image_path.as_posix())

    draw = ImageDraw.Draw(image)

    font = ImageFont.truetype(font_path.as_posix(), font_size)

    title_text = input_text if input_text.isupper() else input_text.title()

    # Center-align text
    wrapped_text = '\n\n'.join(
        (line.center(max_line_length) for line in textwrap.wrap(title_text,
                                                                width=max_line_length)))
    text_width, text_height = draw.textbbox((0, 0), wrapped_text, font=font)[2:]

    text_width, text_height = draw.textbbox((0, 0), wrapped_text, font=font)[2:]

    # Calculate position to center the text in the specified region
    x_position = (region_width + omit_start_width - text_width) // 2
    y_position = (region_height - text_height) // 2

    draw.text((x_position, y_position), wrapped_text, font=font, fill=fill_color)

    image.save(output_file)


def update_trigger_file(notes_repo, trigger_file, updates_exist):
    """Update the trigger file in the notes repository with the current timestamp.

    Args:
        notes_repo: The GitHub repository object for the notes repository.
        trigger_file: The trigger file to be updated
        updates_exist dict: A dict file to decide if there are any updated notes

    Returns:
        str: The updated content of the trigger file with the current timestamp.
    """
    file_content = (notes_repo.get_contents(trigger_file)
                    .decoded_content.decode())

    current_datetime = datetime.now()
    formatted_datetime = current_datetime.strftime('%Y-%m-%d %H:%M:%S')
    if updates_exist:
        new_content_to_add = f'\n Covers Updated on {formatted_datetime}'
    else:
        new_content_to_add = f'\n No covers were updated: {formatted_datetime}'
    return file_content + new_content_to_add


class GithubCommitter:
    """Class to commit files"""

    def __init__(self, git_repo, branch_name):
        """
        Initialize the GithubCommitter class.

        Args:
            access_token (str): Your GitHub access token.
            username (str): Your GitHub username.
            repo_name (str): The name of the repository you want to work with.
        """
        self.repo = git_repo
        self.branch = self.repo.get_branch(branch_name)

    def commit_files(self, file_paths):
        """
        Commit new or updated files to the GitHub repository.

        Args:
            file_paths (dict): A dictionary where keys are local file paths
            and values are corresponding Git file paths.
        """
        main_ref = self.repo.get_git_ref('heads/main')
        main_sha = main_ref.object.sha
        blobs_list = []
        tree_list = []
        for idx, (git_path, local_path) in enumerate(file_paths.items()):
            print(f'Processing: {Path(git_path).name}')
            if str(local_path).endswith('.png'):
                with open(local_path, 'rb') as new_i:
                    image_content = new_i.read()
                encoded_content = base64.b64encode(image_content).decode('utf-8')
                new_blob = self.repo.create_git_blob(content=encoded_content, encoding='base64')
            else:
                with open(local_path, 'r+', encoding='utf-8') as new_f:
                    file_content = new_f.read()
                new_blob = self.repo.create_git_blob(content=file_content, encoding='utf-8')
            blobs_list.append(new_blob)
            tree_element = InputGitTreeElement(path=git_path, mode="100644",
                                               type="blob", sha=blobs_list[idx].sha)
            tree_list.append(tree_element)

        new_tree = self.repo.create_git_tree(tree=tree_list,
                                             base_tree=self.repo.get_git_tree(sha=main_sha))
        self.create_commit_and_push(new_tree, main_ref)

    def create_commit_and_push(self, new_tree, main_ref):
        """
        create_commit_and_push
        """
        # Create a new commit with that tree on top of the current branch head
        commit = self.repo.create_git_commit(
            message=COMMIT_MSG,
            tree=self.repo.get_git_tree(sha=new_tree.sha),
            parents=[self.repo.get_git_commit(self.branch.commit.sha)],
        )

        main_ref.edit(sha=commit.sha)


class GitNotesCoverChecker:
    """Class to commit files"""

    def __init__(self, access_token) -> None:
        """
        Initialize the GithubCommitter class.

        Args:
            access_token (str): Your GitHub access token."""
        self.github = Github(access_token)
        self.repo_notes = self.github.get_repo(f"{GITHUB_USERNAME}/{NOTES_REPO}")
        self.repo_covers = self.github.get_repo(f"{GITHUB_USERNAME}/{COVER_REPO}")
        self.publish_flag = False
        self.journal_flag = False
        self.tmpdir = Path(tempfile.mkdtemp())

    def files_from_last_commit(self):
        """
        get files from last commit in the repo
        """
        notes_main_ref = self.repo_notes.get_git_ref(f'heads/{BRANCH}')
        notes_main_sha = notes_main_ref.object.sha
        notes_commit = self.repo_notes.get_commit(notes_main_sha)
        return notes_commit.files

    def get_updated_files_png(self, notes_files):
        """
        get dicts of files and png

        Args:
            notes_files: Your GitHub access token."""
        png_files = {}
        updated_notes = {}
        for note_file in notes_files:
            filename = note_file.filename
            if filename.endswith(".md") and note_file.status not in ('removed', 'renamed', 'deleted'):
                if filename.startswith('publish/'):
                    self.publish_flag = True
                if filename.startswith('journal/'):
                    self.journal_flag = True
                content = self.repo_notes.get_contents(filename).decoded_content.decode()
                title, png_name, new_content = update_properties(filename, content)
                if new_content:
                    md_path = self.tmpdir / filename
                    md_path.parent.mkdir(parents=True, exist_ok=True)
                    md_path.write_text(new_content, encoding='utf-8')
                    updated_notes[filename] = md_path
                if png_name:
                    png_path = self.tmpdir / png_name
                    create_image(title, png_path)
                    png_files[f'{COVERS_DIR}{png_name}'] = png_path
            else:
                if filename.startswith('publish/'):
                    self.publish_flag = True
                if filename.startswith('journal/'):
                    self.journal_flag = True

        return png_files, updated_notes

    def add_triggers(self, trigger_file, files_dict, png_dict):
        """
        update trigger files and dicts for push

        Args:
            trigger_file: publish/journal trigger file path
            files_dict: dict to be updated
            png_dict: dict to decide on file updates"""
        new_pub_trigger_content = update_trigger_file(self.repo_notes, trigger_file, png_dict)
        trigger_publish_path = self.tmpdir / trigger_file
        trigger_publish_path.parent.mkdir(parents=True, exist_ok=True)
        trigger_publish_path.write_text(new_pub_trigger_content, encoding='utf-8')
        files_dict[trigger_file] = trigger_publish_path
        return files_dict

    def run_cover_checker(self):
        """
        Function to get files from last commit in notes repo and check for cover image
        and create cover image if not exist and push the files to repos
        """
        notes_files = self.files_from_last_commit()
        png_files_dict, updated_notes_dict = self.get_updated_files_png(notes_files)
        if self.publish_flag:
            updated_notes_dict = self.add_triggers(PUBLISH_TRIGGER_FILE, updated_notes_dict, png_files_dict)
        if self.journal_flag:
            updated_notes_dict = self.add_triggers(JOURNAL_TRIGGER_FILE, updated_notes_dict, png_files_dict)
        if png_files_dict:
            covers_committer = GithubCommitter(self.repo_covers, BRANCH)
            covers_committer.commit_files(png_files_dict)
        notes_committer = GithubCommitter(self.repo_notes, BRANCH)
        notes_committer.commit_files(updated_notes_dict)


# Example usage
if __name__ == "__main__":
    github_token = os.getenv("GITHUB_TOKEN")

    gc = GitNotesCoverChecker(github_token)
    gc.run_cover_checker()
