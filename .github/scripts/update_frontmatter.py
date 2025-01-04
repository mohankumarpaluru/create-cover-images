#!/usr/bin/env python3

"""
Script to generate open graph images for markdown files and update markdown content with image url
"""

import base64
import os
import re
import tempfile
from datetime import datetime
from io import StringIO
from pathlib import Path

from github import Github, InputGitTreeElement
from ruamel.yaml import YAML

# Helper constants
COMMIT_MSG = "Updating Front Matter and Deploying"
BRANCH = "main"
GITHUB_USERNAME = "mohankumarpaluru"
NOTES_REPO = "notes"
PUBLISH_TRIGGER_FILE = '.github/trigger_files/publish.txt'
JOURNAL_TRIGGER_FILE = '.github/trigger_files/journal.txt'


def remove_extension(filename):
    """Remove file extension from a filename."""
    return re.sub(r'\.[^.]+$', '', filename)


def split_words(filename):
    """Split a filename into words based on common delimiters and casing."""
    return re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+', filename)


def process_word(word):
    """Process a single word based on its casing."""
    if word.isupper() and len(word) > 1:
        return word  # Acronyms
    if word.isdigit():
        return word  # Numbers
    return word.capitalize()  # Default: Capitalize first letter


def generate_title(filename):
    """Generate a title from the filename."""
    base_name = remove_extension(filename).replace('_', ' ').replace('-', ' ')
    return ' '.join([word.title() if not word.isupper() else word for word in base_name.split()])


def generate_description(filename):
    """Generate a description from the filename."""
    base_name = remove_extension(filename)
    words = split_words(base_name)
    return ' '.join(process_word(word) for word in words)


def update_properties(file_path=None, file_content=None):
    """
    Update markdown properties for title, description, and date.

    Args:
        file_path (Path or str): Path to the Markdown file.
        file_content (str): Markdown content as a string.

    Returns:
        str: Updated Markdown content.
    """
    if file_path:
        file_path = Path(file_path)
        if not file_content and file_path.is_file():
            with file_path.open('r', encoding='utf-8') as md_file:
                file_content = md_file.read()

    if file_content is None:
        raise ValueError("Either file_path or file_content must be provided.")

    current_date = datetime.now().strftime("%Y-%m-%d")
    yaml = YAML()
    yaml.default_flow_style = False

    # Extract existing front matter
    match = re.search(r'^\s*---(.*?)---', file_content, re.DOTALL)
    if match:
        properties = yaml.load(match.group(1)) or {}
    else:
        properties = {}

    # Update or set title, description, and date
    if 'title' not in properties:
        properties['title'] = generate_title(file_path.stem) if file_path else "Untitled"
    if 'description' not in properties:
        properties['description'] = generate_description(file_path.stem) if file_path else ""
    properties['date'] = current_date

    # Use a stream for YAML output
    updated_props_stream = StringIO()
    yaml.dump(properties, updated_props_stream)
    updated_props_stream.seek(0)
    updated_front_matter = f"---\n{updated_props_stream.read().strip()}\n---\n"

    if match:
        updated_content = re.sub(r'^\s*---(.*?)---', updated_front_matter, file_content, count=1, flags=re.DOTALL)
    else:
        updated_content = updated_front_matter + "\n" + file_content.strip()

    return updated_content


def generate_trigger_file_content():
    """
    TO generate current date time stamp for trigger file content

    Returns:
        str: The updated content of the trigger file with the current timestamp.
    """
    current_datetime = datetime.now()
    formatted_datetime = current_datetime.strftime('%Y-%m-%d %H:%M:%S')
    new_content_to_add = f'\n Front Matter Updated on {formatted_datetime}'
    return new_content_to_add


class GithubCommitter:
    """Class to commit files"""

    def __init__(self, git_repo, branch_name):
        """
        Initialize the GithubCommitter class.

        Args:
            git_repo: The GitHub repository object.
            branch_name:  The name of the branch to commit to.
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


class GitNotesFrontMatterHandler:
    """Class to commit files"""

    def __init__(self, access_token) -> None:
        """
        Initialize the GithubCommitter class.

        Args:
            access_token (str): Your GitHub access token."""
        self.github = Github(access_token)
        self.repo_notes = self.github.get_repo(f"{GITHUB_USERNAME}/{NOTES_REPO}")
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

    def get_updated_files(self, notes_files):
        """
        get dicts of files and png

        Args:
            notes_files: Your GitHub access token.
        Returns:
            dict: A dictionary of updated notes files.
        """

        updated_notes = {}
        for note_file in notes_files:
            filename = note_file.filename
            if filename.endswith(".md") and note_file.status not in ('removed', 'renamed', 'deleted'):
                if filename.startswith('publish/'):
                    self.publish_flag = True
                if filename.startswith('journal/'):
                    self.journal_flag = True
                content = self.repo_notes.get_contents(filename).decoded_content.decode()
                new_content = update_properties(filename, content)
                if new_content:
                    md_path = self.tmpdir / filename
                    md_path.parent.mkdir(parents=True, exist_ok=True)
                    md_path.write_text(new_content, encoding='utf-8')
                    updated_notes[filename] = md_path
            else:
                if filename.startswith('publish/'):
                    self.publish_flag = True
                if filename.startswith('journal/'):
                    self.journal_flag = True

        return updated_notes

    def add_triggers(self, trigger_file, files_dict):
        """
        update trigger files and dicts for push

        Args:
            trigger_file: publish/journal trigger file path
            files_dict: dict to be updated
        Returns:
            dict: A dictionary of updated files.
        """
        if trigger_file in files_dict:
            return files_dict
        new_pub_trigger_content = generate_trigger_file_content()
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
        updated_notes_dict = self.get_updated_files(notes_files)
        if self.publish_flag:
            updated_notes_dict = self.add_triggers(PUBLISH_TRIGGER_FILE, updated_notes_dict)
        if self.journal_flag:
            updated_notes_dict = self.add_triggers(JOURNAL_TRIGGER_FILE, updated_notes_dict)
        notes_committer = GithubCommitter(self.repo_notes, BRANCH)
        notes_committer.commit_files(updated_notes_dict)


# Example usage
if __name__ == "__main__":
    github_token = os.getenv("GITHUB_TOKEN")

    gc = GitNotesFrontMatterHandler(github_token)
    gc.run_cover_checker()
