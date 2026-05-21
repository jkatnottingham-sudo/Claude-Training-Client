from anthropic_client import add_assistant_message, add_user_message, chat
from anthropic import Anthropic

client = Anthropic()
model = "claude-haiku-4-5"

def main() -> None:
    messages: list[dict[str, str]] = []
    
    input_message = input("Enter your message: ")
        # if input_message == "exit" or input_message == "quit"  or input_message == "bye" or input_message == "ok bye":
        #     print("Bye bro! See you next time!")
        #     break
 
    add_user_message(messages, input_message)
    
    add_assistant_message(messages, "```bash")

    # with client.messages.stream(
    #     model=model,
    #     max_tokens=1000,
    #     messages=messages,
    #     stop_sequences=[ "```"],
    #     #system = "Remove ```json and ``` at the beginning and end of the response."
    # ) as stream:
    #     for text in stream.text_stream:
    #         print(text, end="")
     
    # response = client.messages.create(
    #     model= model,
    #     max_tokens= 1000,
    #     messages= messages,
    #     temperature= 0.1,
    #     system="Put all AWS CLI commands on a single line, separated by && .",
    #     stop_sequences=["```"]
    # )
    response=chat(messages, stop_sequences=["```"])
    
    print(response)
    print(response.content[0].text.strip("\n"))

if __name__ == "__main__":
    main()
