import os
import re
import yaml
from PIL import Image, ImageDraw, ImageFont
from github import Github

def create_image(text, output_path):
    width, height = 720, 1020
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    text_width, text_height = draw.textsize(text, font)
    x = (width - text_width) // 2
    y = (height - text_height) // 2

    draw.text((x, y), text, fill="black", font=font)
    image.save(output_path)

def main():
    github_token = os.getenv("GITHUB_TOKEN")
    repo = Github(github_token).get_repo("mohankumarpaluru/create-cover-images")

    commit_sha = os.getenv("GITHUB_SHA")
    commit = repo.get_commit(commit_sha)
    files = commit.files

    for file in files:
        if file.filename.endswith(".md"):
            content = repo.get_contents(file.filename).decoded_content.decode("utf-8")

            match = re.search(r"---\n(.*?)(?:\n---|\.\.\.)", content, re.DOTALL)
            if match:
                front_matter = match.group(1)
                yaml_data = yaml.safe_load(front_matter)

                if "ogImage" in yaml_data:
                    og_image_data = yaml_data["ogImage"]
                    if "text" in og_image_data and "url" not in og_image_data:
                        text = og_image_data["text"]
                        image_path = f"public/assets/blog/covers/{file.filename.replace('.md', '.png')}"
                        create_image(text, image_path)

                        # Push the image to the repository
                        repo.create_file(image_path, f"Add cover image for {file.filename}", image_path)

                        # Update the markdown with the image URL
                        image_url = f"https://cdn.jsdelivr.net/gh/mohankumarpaluru/create-cover-images@{commit_sha}/{image_path}"
                        content = content.replace(f"ogImage:\n    text: {text}", f"ogImage:\n    url: {image_url}")

                        # Update the file in the repository
                        repo.update_file(file.filename, f"Update ogImage in {file.filename}", content, file.sha)

if __name__ == "__main__":
    main()
