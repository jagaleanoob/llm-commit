#!/usr/bin/env python3
import sys
import subprocess
from typing import List, Tuple
import os
from anthropic import Anthropic
import json

class GitCommitHelper:
    def __init__(self):
        self.anthropic = Anthropic(
            api_key=os.getenv('ANTHROPIC_API_KEY')
        )

    def get_staged_changes(self) -> List[Tuple[str, str, str]]:
        """
        Get the staged changes from git.
        """
        try:
            staged_files = subprocess.check_output(
                ['git', 'diff', '--cached', '--name-only'],
                universal_newlines=True
            ).split('\n')
            staged_files = [f for f in staged_files if f]

            changes = []
            for file_path in staged_files:
                diff = subprocess.check_output(
                    ['git', 'diff', '--cached', file_path],
                    universal_newlines=True
                )
                
                try:
                    with open(file_path, 'r') as f:
                        file_content = f.read()
                except:
                    file_content = ""

                changes.append((file_path, diff, file_content))
            
            return changes
        except subprocess.CalledProcessError:
            print("Error: Not a git repository or git is not installed")
            sys.exit(1)

    def prepare_claude_prompt(self, changes: List[Tuple[str, str, str]]) -> str:
        """
        Prepare a prompt for Claude to analyze the changes and generate a commit message.
        """
        prompt = """You are a helpful assistant that generates descriptive git commit messages. 
        Analyze the following changes and generate a clear, informative commit message that describes what was changed and why.
        Focus on the functional changes and their impact. Use the active voice and present tense.

        Just answer directly with the commit text.
        
        The commit message should follow this format:
        - First line: Short summary (50-72 characters)
        - Second line: Blank
        - Following lines: Detailed explanation if needed
        
        Here are the changes:\n\n"""

        for file_path, diff, content in changes:
            prompt += f"File: {file_path}\n"
            prompt += f"Diff:\n{diff}\n"
            prompt += f"Current file content:\n{content}\n\n"

        prompt += "\nBased on these changes, generate a commit message that explains what was changed and why."
        return prompt

    def get_commit_message_from_claude(self, changes: List[Tuple[str, str, str]]) -> str:
        """
        Use Claude API to generate a descriptive commit message based on the changes.
        """
        try:
            prompt = self.prepare_claude_prompt(changes)
            
            message = self.anthropic.messages.create(
                model="claude-3-5-sonnet-latest",
                max_tokens=1000,
                temperature=0.7,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            return message.content

        except Exception as e:
            print(f"Error calling Claude API: {str(e)}")
            return self.generate_fallback_message(changes)

    def generate_fallback_message(self, changes: List[Tuple[str, str, str]]) -> str:
        """
        Generate a basic commit message if Claude API fails.
        """
        if len(changes) == 1:
            file_path = changes[0][0]
            return f"Update {file_path}"
        else:
            return f"Update {len(changes)} files"

    def create_commit(self, message: str) -> None:
        """
        Create a git commit with the generated message.
        """
        try:
            subprocess.run(['git', 'commit', '-m', message], check=True)
            print(f"Successfully created commit with message:\n{message}")
        except subprocess.CalledProcessError:
            print("Error: Failed to create commit")
            sys.exit(1)

    def run(self):
        # Check for API key
        if not os.getenv('ANTHROPIC_API_KEY'):
            print("Error: ANTHROPIC_API_KEY environment variable not set")
            sys.exit(1)

        changes = self.get_staged_changes()
        
        if not changes:
            print("No changes staged for commit")
            sys.exit(0)
            
        commit_message = self.get_commit_message_from_claude(changes)
        
        print("\nSuggested commit message:")
        print(f'"""\n{commit_message[0].text}\n"""')
        
        confirmation = input("\nDo you want to create this commit? (y/n/e[edit]): ")
        if confirmation.lower() == 'y':
            self.create_commit(commit_message[0].text)
        elif confirmation.lower() == 'e':
            # Open editor for message modification
            with open('.git/COMMIT_EDITMSG', 'w') as f:
                f.write(commit_message)
            subprocess.run(['git', 'commit', '-e'], check=True)
        else:
            print("Commit cancelled")

if __name__ == "__main__":
    helper = GitCommitHelper()
    helper.run()
