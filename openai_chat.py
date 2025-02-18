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
    
def remove_thinking_part(text):
    # This pattern matches any section that starts with <think> and ends with <end_think>, or any other relevant format
    trimmed_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)  # Removing <think> tags and content between
    trimmed_text = trimmed_text.strip()  # Clean up leading/trailing whitespace
    return trimmed_text


class LocalAiManager:
    def __init__(self):
        self.chat_history = []  # Stores the entire conversation

    def _ask_local_model(self, prompt):
        """Send a request to the local Ollama model."""
        try:
            # Send the prompt to the Ollama model (deepseek-r1)
            response = ollama.chat(
                model="deepseek-r1:8b", # needs to be changed to the local model!!!!!
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
        # Remove thinking parts before passing it to ElevenLabs
            clean_answer = remove_thinking_part(openai_answer)
            print(f"[green]\n{clean_answer}\n")

        # Send the cleaned response to ElevenLabs
        return clean_answer

    def chat_with_history(self, prompt=""):
        if not prompt:
            print("Didn't receive input!")
            return

        # Add the prompt into the chat history
        self.chat_history.append({"role": "user", "content": prompt})

        # Check total token limit and remove old messages as needed
        print(f"[coral]Chat History has a current token length of {num_tokens_from_messages(self.chat_history)}")
        while num_tokens_from_messages(self.chat_history) > 8000:
            self.chat_history.pop(1)  # We skip the 1st message since it's the system message
            print(f"Popped a message! New token length is: {num_tokens_from_messages(self.chat_history)}")

        print("[yellow]\nAsking Local Model a question...")
        chat_history_text = "\n".join([message["content"] for message in self.chat_history])
        openai_answer = self._ask_local_model(chat_history_text)

        if openai_answer:
        # Remove thinking parts before passing it to ElevenLabs
            clean_answer = remove_thinking_part(openai_answer)

        # Add this clean answer to the chat history
            self.chat_history.append({"role": "assistant", "content": clean_answer})

        print(f"[green]\n{clean_answer}\n")

        return clean_answer
    
    def print_chat_history(self):
        """Prints the entire chat history."""
        print("\n[blue]Full Chat History:")
        for index, message in enumerate(self.chat_history):
            role = message["role"]
            content = message["content"]
            print(f"Message {index + 1}: [{role}] {content}\n")

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
        local_ai_manager.chat_with_history(new_prompt)
        local_ai_manager.print_chat_history()