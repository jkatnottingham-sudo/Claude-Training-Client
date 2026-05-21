from anthropic_client import add_assistant_message, add_user_message, chat


def main() -> None:
    messages: list[dict[str, str]] = []
    
    print("--------------------------------")
    #system_prompt = input("Enter your system prompt: ")
    system_prompt = ""
    while True:
        input_message = input("Enter your message: ")
        if input_message == "exit" or input_message == "quit"  or input_message == "bye" or input_message == "ok bye":
            print("Bye bro! See you next time!")
            break
        add_user_message(messages, input_message)

        response = chat(messages, system_prompt)
        print(response)
        #add_assistant_message(messages, response)
        
if __name__ == "__main__":
    main()
