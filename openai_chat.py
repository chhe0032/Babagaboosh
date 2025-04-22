import ollama
import tiktoken
import re
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
    

class LocalAiManager:
    def __init__(self):
        self.chat_history = []  # Stores the entire conversation

    def _ask_local_model(self, prompt):
        """Send a request to the local Ollama model."""
        try:
            # Send the prompt to the Ollama model (deepseek-r1)
            response = ollama.chat(
                model="qwq:32b", # needs to be changed to the local model!!!!!
                messages=[{"role": "user", "content": prompt}],
                stream=False  # Non-streaming response
            )
            return response["message"]["content"]  # Extracting the message content from the response
        except Exception as e:
            print(f"Error interacting with Ollama: {e}")
            return None

    def chat(self, prompt=""):
        if not prompt:
            print("Didn't receive input!")
            return

        # Check if the prompt is under the token context limit (same as before)
        chat_question = [{"role": "user", "content": prompt}]
        if num_tokens_from_messages(chat_question) > 8000:
            print("The length of this chat question is too large for the model")
            return

        print("[yellow]\nAsking Local Model a question...")
        openai_answer = self._ask_local_model(prompt)

        if openai_answer:
            # Return the full answer without removing any thinking parts
            print(f"[green]\n{openai_answer}\n")
            return openai_answer

    def chat_with_history(self, payload):
        if not payload.get('prompt') and not payload.get('image'):
            print("Didn't receive input!")
            return None

        # Prepare the user message content
        user_message_content = payload.get('prompt', '')
    
        # Add context if available
        if payload.get('context'):
            self.chat_history.append({
                "role": "system", 
                "content": f"Chat context:\n{payload['context']}"
        })

        # Build the user message
        user_message = {
            "role": "user",
            "content": user_message_content
        }
    
        if payload.get('image'):
            user_message["images"] = [payload['image']]

        # Add to chat history
        self.chat_history.append(user_message)

        for msg in self.chat_history:
            if "images" in msg and msg is not user_message:
                del msg["images"]

        # Check token limit (using string representation for token counting)
        while num_tokens_from_messages([{"content": str(msg.get('content', ''))} for msg in self.chat_history]) > 8000:
            self.chat_history.pop(1)
            print(f"Popped a message! New token length: {num_tokens_from_messages(self.chat_history)}")

        # Call Ollama
        print("[yellow]\nAsking Local Model a question...")
        try:
            response = ollama.chat(
                model="qwq:32b",  # needs to be changed to the local model!!!!!
                messages=self.chat_history,
                stream=False
            )
            # Use the full response without removing thinking parts
            full_answer = response["message"]["content"]
            self.chat_history.append({"role": "assistant", "content": full_answer})
            return full_answer
        except Exception as e:
            print(f"Error interacting with Ollama: {e}")
        return None

    def print_chat_history(self):
        """Helper method to print the chat history"""
        for message in self.chat_history:
            role = message["role"]
            content = message["content"]
            print(f"[{'blue' if role == 'user' else 'green'}]{role}: {content}\n")

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