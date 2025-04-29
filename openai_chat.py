import ollama
import tiktoken
import re
import os
import datetime
from pathlib import Path
from rich import print


def num_tokens_from_messages(messages, model='ollama'):
    """Returns the number of tokens used by a list of messages."""
    try:
        if model == 'ollama':
            # Handle the 'ollama' case separately (provide a fallback tokenizer or logic here)
            num_tokens = sum(len(message["content"].split()) for message in messages)  # Just a fallback example
        else:
            # Default to tiktoken for models that are supported
            encoding = tiktoken.encoding_for_model(model)
            num_tokens = 0
            for message in messages:
                num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
                for key, value in message.items():
                    num_tokens += len(encoding.encode(value))
                    if key == "name":
                        num_tokens += -1  # role is always required and always 1 token
            num_tokens += 2  # every reply is primed with <im_start>
        return num_tokens
    except Exception as e:
        print(f"Error: {str(e)}")
        raise NotImplementedError(f"num_tokens_from_messages() is not presently implemented for model {model}.")

def remove_thinking_part(text):
    # This pattern matches any section that starts with <think> and ends with <end_think>, or any other relevant format
    trimmed_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)  # Removing <think> tags and content between
    trimmed_text = trimmed_text.strip()  # Clean up leading/trailing whitespace
    return trimmed_text

    

class LocalAiManager:
    def __init__(self):
        self.chat_history = []  # Stores the entire conversation
        self.backup_file = "conversation_backup.txt"  # Permanent backup file
        self._initialize_backup()
    
    def _initialize_backup(self):
        """Create backup file if it doesn't exist"""
        if not os.path.exists(self.backup_file):
            with open(self.backup_file, 'w') as f:
                f.write("=== Conversation Backup ===\n")
    
    def _save_to_backup(self, role, content):
        """Append a message to the backup file with timestamp"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.backup_file, 'a', encoding='utf-8') as f:
            f.write(f"\n[{timestamp}] {role}:\n{content}\n")
            f.write("-" * 40 + "\n")  # Separator line

    def _ask_local_model(self, prompt):
        """Send a request to the local Ollama model."""
        try:
            # Save the user prompt to backup
            self._save_to_backup("USER", prompt)
            
            # Send the prompt to the Ollama model
            response = ollama.chat(
                model="qwq:32b",
                messages=[{"role": "user", "content": prompt}],
                stream=False
            )
            full_response = response["message"]["content"]
            
            # Save the full response (including thinking parts) to backup
            self._save_to_backup("ASSISTANT (FULL)", full_response)
            
            return full_response
        except Exception as e:
            print(f"Error interacting with Ollama: {e}")
            return None

    def chat(self, prompt=""):
        if not prompt:
            print("Didn't receive input!")
            return

        # Check token limit
        chat_question = [{"role": "user", "content": prompt}]
        if num_tokens_from_messages(chat_question) > 8000:
            print("The length of this chat question is too large for the model")
            return

        print("[yellow]\nAsking Local Model a question...")
        full_response = self._ask_local_model(prompt)

        if full_response:
            clean_answer = remove_thinking_part(full_response)
            print(f"[green]\n{clean_answer}\n")
            # Save the cleaned response to backup as well
            self._save_to_backup("ASSISTANT (CLEAN)", clean_answer)
            return clean_answer

    def chat_with_history(self, payload):
        if not payload.get('prompt') and not payload.get('image'):
            print("Didn't receive input!")
            return None

        # Prepare and save user message
        user_message_content = payload.get('prompt', '')
        self._save_to_backup("USER", user_message_content)
    
        # Add context if available
        if payload.get('context'):
            context_message = {
                "role": "system", 
                "content": f"Chat context:\n{payload['context']}"
            }
            self.chat_history.append(context_message)
            self._save_to_backup("SYSTEM", context_message["content"])

        # Build the user message
        user_message = {
            "role": "user",
            "content": user_message_content
        }
    
        if payload.get('image'):
            user_message["images"] = [payload['image']]

        # Add to chat history
        self.chat_history.append(user_message)

        # Clean images from previous messages
        for msg in self.chat_history:
            if "images" in msg and msg is not user_message:
                del msg["images"]

        # Check token limit
        while num_tokens_from_messages([{"content": str(msg.get('content', ''))} for msg in self.chat_history]) > 8000:
            removed = self.chat_history.pop(1)
            print(f"Popped a message! New token length: {num_tokens_from_messages(self.chat_history)}")
            self._save_to_backup("SYSTEM", f"Removed message due to token limit: {removed['content']}")

        # Call Ollama
        print("[yellow]\nAsking Local Model a question...")
        try:
            response = ollama.chat(
                model="qwq:32b",
                messages=self.chat_history,
                stream=False
            )
            full_response = response["message"]["content"]
            clean_answer = remove_thinking_part(full_response)
            
            # Save both versions to backup
            self._save_to_backup("ASSISTANT (FULL)", full_response)
            self._save_to_backup("ASSISTANT (CLEAN)", clean_answer)
            
            # Add cleaned version to chat history
            self.chat_history.append({"role": "assistant", "content": clean_answer})
            
            return clean_answer
        except Exception as e:
            print(f"Error interacting with Ollama: {e}")
            self._save_to_backup("SYSTEM", f"Error: {str(e)}")
        return None

if __name__ == '__main__':
    local_ai_manager = LocalAiManager()

    # CHAT TEST
    #chat_without_history = local_ai_manager.chat("Hey, what is 2 + 2? But tell it to me as Yoda")

    # CHAT WITH HISTORY TEST
    FIRST_SYSTEM_MESSAGE = {"role": "system", "content": "Act like you are Captain Jack Sparrow from the Pirates of the Caribbean movie series!"}
    FIRST_USER_MESSAGE = {"role": "user", "content": "Ahoy there! Who are you, and what are you doing in these parts? Please give me a 1 sentence background on how you got here."}
    local_ai_manager.chat_history.append(FIRST_SYSTEM_MESSAGE)
    local_ai_manager.chat_history.append(FIRST_USER_MESSAGE)

    while True:
        new_prompt = input("\nType out your next question Jack Sparrow, then hit enter: \n\n")
        # The payload should be a dictionary with at least a 'prompt' key
        local_ai_manager.chat_with_history({'prompt': new_prompt})
        local_ai_manager.print_chat_history()