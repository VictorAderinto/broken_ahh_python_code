import os
import json
import re
from typing import Dict, List, Optional, Union, TypedDict, Any

import cohere
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Use Cohere's model
MODEL = "command-r-plus"  # Using Cohere's powerful model

api_key = os.environ.get("COHERE_API_KEY")
print(f"API Key found: {'Yes' if api_key else 'No'}")

# Initialize the Cohere client
client = cohere.Client(api_key=api_key)

# Type definitions similar to the TypeScript interfaces
class StudyPermitData(TypedDict, total=False):
    personalInfo: Dict[str, Any]
    education: Dict[str, Any]
    financialInfo: Dict[str, Any]
    travelHistory: Dict[str, Any]
    documents: Dict[str, Any]

class ChatMessage(TypedDict):
    role: str  # "system" | "user" | "assistant"
    content: str

class AIChatResponse(TypedDict, total=False):
    message: str
    collectedData: Dict[str, Any]
    action: str
    options: List[str]
    formPreview: Dict[str, Any]

# System message to configure the AI assistant's behavior
system_message = """
You are imm.ai, an advanced immigration assistant specialized in helping applicants through the Canadian immigration process. 

Your primary role is to guide applicants through their work permit application by:
1. Collecting necessary personal, professional, financial, and travel information through conversational interviews
2. Explaining immigration requirements clearly and in simple language
3. Detecting potential issues or inconsistencies in the applicant's information
4. Filling out immigration forms accurately based on collected information
5. Providing helpful resources and guidance throughout the process

IMPORTANT GUIDELINES:

1. Only ask ONE question at a time. Wait for the user's response before asking the next question.
   Do not group multiple questions together. This is critical for our users who may get overwhelmed by many questions at once.

2. AUTOMATIC SECTION TRANSITIONS:
   - When you've collected all information for a section, clearly indicate that the section is complete.
   - Then AUTOMATICALLY transition to the next section without waiting for the user to ask for it.
   - Let the user know which section you're moving to next.
   - Example: "Great! I've collected all the personal information I need. Now, let's move on to your educational background..."

3. SECTION COMPLETION NOTIFICATION:
   - At the end of each section, summarize the information collected for that section
   - Then inform the user that this section is complete and you're advancing to the next one
   - This helps the user understand their progress through the application

Your tone should be:
- Professional but friendly
- Clear and concise
- Empathetic and patient
- Non-judgmental

You will interview the user following a structured process covering these key areas in sequence:
1. Personal information (name, date of birth, nationality, passport details)
2. Professional background (job offer, employer details, work experience)
3. Financial information (proof of funds, financial support)
4. Travel history (previous visa applications, entries to Canada)
5. Document preparation (required supporting documents)
6. Final review and summary

Always respond in the same language as the user's messages. If you're unsure of language, respond in English.

After completing each section, automatically progress to the next one without waiting for user prompting.

When you need to show a form preview or summary, specify this in your JSON response.

After collecting all necessary information, help users prepare their complete application package.
"""

def get_system_prompt(language: str) -> str:
    """Add language-specific instructions to the system prompt."""
    prompt = system_message
    
    # Add language preference if not English
    if language and language != "en":
        language_names = {
            "fr": "French (Français)",
            "es": "Spanish (Español)",
            "zh": "Chinese (中文)",
            "hi": "Hindi (हिंदी)"
        }
        
        language_name = language_names.get(language, language)
        prompt += f"\nThe user prefers communication in {language_name}. Please provide all responses in {language_name} when possible."
    
    return prompt

async def generate_chat_response(
    messages: List[ChatMessage],
    collected_data: Optional[Dict[str, Any]] = None,
    language: str = "en"
) -> AIChatResponse:
    """Generate a response using the Cohere API."""
    # Get AI response
    try:
        # Transform messages for Cohere's format
        cohere_messages = []
        for msg in messages:
            role = msg["role"]
            # Map roles to Cohere's format (Cohere uses "USER" and "CHATBOT")
            if role == "user":
                cohere_role = "USER"
            elif role == "assistant":
                cohere_role = "CHATBOT"
            else:
                continue  # Skip system messages as they're handled separately
            
            cohere_messages.append({
                "role": cohere_role,
                "message": msg["content"]
            })
        
        # Add context about already collected data
        preamble = get_system_prompt(language)
        
        if collected_data and len(collected_data) > 0:
            preamble += f"\n\nInformation collected so far:\n{json.dumps(collected_data, indent=2)}"
        
        # Language detection
        if len(messages) > 0:
            last_user_messages = [msg for msg in reversed(messages) if msg["role"] == "user"]
            if last_user_messages:
                preamble += """\n\nIf the user's message is clearly in a different language than what you've been using,
                    respond in that language. Always prioritize clear communication over strict language adherence."""
        
        try:
            response = client.chat(
                model=MODEL,
                message=cohere_messages[-1]["message"] if cohere_messages else "",
                chat_history=[m for m in cohere_messages[:-1]] if len(cohere_messages) > 1 else [],
                temperature=0.7,
                preamble=preamble,
                max_tokens=1000,
            )

            # Try to parse the response as JSON
            try:
                # Extract text content from response
                response_text = response.text if hasattr(response, 'text') else str(response)

                # Check if the response contains a JSON object
                json_match = re.search(r'```json\n([\s\S]*?)\n```|{[\s\S]*?}', response_text)
                
                if json_match:
                    json_str = json_match.group(1) or json_match.group(0)
                    parsed_response = json.loads(json_str)
                    # If the parsed JSON doesn't have a message field, add the content
                    if "message" not in parsed_response:
                        parsed_response["message"] = response_text
                    return parsed_response
                
                # No valid JSON found, return the text as message
                return {"message": response_text}
            except Exception as error:
                # If JSON parsing fails, return the raw message
                print(f"Failed to parse AI response as JSON: {error}")
                return {"message": response.text if hasattr(response, 'text') else str(response)}
        except Exception as cohere_error:
            # Handle Cohere API errors
            print(f"Cohere API error: {cohere_error}")
            
            # Provide a fallback response when Cohere API fails
            fallback_message = "I'm sorry, I encountered technical difficulties processing your request."
            action = "continue"
            
            # Analyze previous messages to provide context-aware fallback
            if len(messages) > 0:
                last_user_messages = [msg for msg in reversed(messages) if msg["role"] == "user"]
                if last_user_messages:
                    last_user_message = last_user_messages[0]["content"].lower()
                    
                    # Provide appropriate fallback based on detected intent
                    if "name" in last_user_message or "call" in last_user_message:
                        fallback_message = "I'm having trouble connecting to our services. It seems you're providing your name, which is an important part of your application. Please try again later when our services are back online."
                    elif any(word in last_user_message for word in ["birth", "born", "age"]):
                        fallback_message = "I'm experiencing connection issues. I understand you're sharing your date of birth, which we'll need for your application. Please try again when our services are restored."
                    elif any(word in last_user_message for word in ["country", "national", "citizen"]):
                        fallback_message = "Our services are temporarily unavailable. I can see you're providing nationality information, which is essential for your application. Please try again later."
                    elif any(word in last_user_message for word in ["educat", "school", "university", "college", "study"]):
                        fallback_message = "I'm currently unable to process your information due to technical issues. It appears you're sharing educational details, which are important for your study permit. Please retry when our systems are back online."
                    elif any(word in last_user_message for word in ["passport", "document", "id"]):
                        fallback_message = "Our systems are temporarily down. I notice you're providing passport or ID information, which we'll need to process your application. Please try again later."
                    elif any(word in last_user_message for word in ["address", "live", "reside"]):
                        fallback_message = "I'm experiencing connectivity problems. It seems you're sharing your address details, which are required for your application. Please try again when our services are back online."
                    elif "thank" in last_user_message:
                        fallback_message = "You're welcome! I'm currently experiencing some technical difficulties, but I'm here to help with your immigration application when our services are restored."
                    elif "hello" in last_user_message or "hi " in last_user_message or last_user_message == "hi":
                        fallback_message = "Hello! I'm imm.ai, your immigration assistant. I'm experiencing technical difficulties at the moment. Please try again shortly, and I'll be happy to help with your application process."
                    elif "show summary" in last_user_message:
                        fallback_message = "I'm unable to generate a summary right now due to technical difficulties. This feature will be available when our services are restored. Please try again later."
                        action = "showSummary"
                    elif any(word in last_user_message for word in ["form", "preview", "download"]):
                        fallback_message = "I can't generate your form preview at the moment due to technical issues. This feature will be available when our services are back online. Please try again later."
                        action = "showFormPreview"
                    else:
                        fallback_message += " Our AI assistant is currently unavailable. Please try again later, or use the 'show summary' command to review information you've already provided."
            
            # Return user-friendly error with appropriate context
            return {
                "message": fallback_message,
                "action": action
            }
    except Exception as error:
        print(f"Error generating chat response: {error}")
        
        # Create intelligent fallback responses based on conversation context
        fallback_message = "I'm sorry, I encountered technical difficulties processing your request."
        action = "continue"
        
        # Analyze previous messages to provide context-aware fallback
        if len(messages) > 0:
            last_user_messages = [msg for msg in reversed(messages) if msg["role"] == "user"]
            if last_user_messages:
                last_user_message = last_user_messages[0]["content"].lower()
                
                # Provide appropriate fallback based on detected intent
                if "name" in last_user_message or "call" in last_user_message:
                    fallback_message = "I'm having trouble connecting to our services. It seems you're providing your name, which is an important part of your application. Please try again later when our services are back online."
                elif any(word in last_user_message for word in ["birth", "born", "age"]):
                    fallback_message = "I'm experiencing connection issues. I understand you're sharing your date of birth, which we'll need for your application. Please try again when our services are restored."
                elif any(word in last_user_message for word in ["country", "national", "citizen"]):
                    fallback_message = "Our services are temporarily unavailable. I can see you're providing nationality information, which is essential for your application. Please try again later."
                elif any(word in last_user_message for word in ["educat", "school", "university", "college", "study"]):
                    fallback_message = "I'm currently unable to process your information due to technical issues. It appears you're sharing educational details, which are important for your study permit. Please retry when our systems are back online."
                elif any(word in last_user_message for word in ["passport", "document", "id"]):
                    fallback_message = "Our systems are temporarily down. I notice you're providing passport or ID information, which we'll need to process your application. Please try again later."
                elif any(word in last_user_message for word in ["address", "live", "reside"]):
                    fallback_message = "I'm experiencing connectivity problems. It seems you're sharing your address details, which are required for your application. Please try again when our services are back online."
                elif "thank" in last_user_message:
                    fallback_message = "You're welcome! I'm currently experiencing some technical difficulties, but I'm here to help with your immigration application when our services are restored."
                elif "hello" in last_user_message or "hi " in last_user_message or last_user_message == "hi":
                    fallback_message = "Hello! I'm imm.ai, your immigration assistant. I'm experiencing technical difficulties at the moment. Please try again shortly, and I'll be happy to help with your application process."
                elif "show summary" in last_user_message:
                    fallback_message = "I'm unable to generate a summary right now due to technical difficulties. This feature will be available when our services are restored. Please try again later."
                    action = "showSummary"
                elif any(word in last_user_message for word in ["form", "preview", "download"]):
                    fallback_message = "I can't generate your form preview at the moment due to technical issues. This feature will be available when our services are back online. Please try again later."
                    action = "showFormPreview"
                else:
                    fallback_message += " Our AI assistant is currently unavailable. Please try again later, or use the 'show summary' command to review information you've already provided."
        
        # Return user-friendly error with appropriate context
        return {
            "message": fallback_message,
            "action": action
        }

async def extract_form_data(
    messages: List[ChatMessage],
    form_type: str = "study_permit",
    language: str = "en"
) -> Dict[str, Any]:
    """Extract structured data from conversation history."""
    try:
        extraction_prompt = f"""
            Based on the conversation history, extract all relevant information for a {form_type} application.
            Format the extracted data as a structured JSON object according to the appropriate schema.
            Only include information that has been explicitly stated by the user.
            For study permit applications, include personal information, educational background, and any other relevant details.
            Your response should ONLY be the JSON object without any additional text.
        """

        # Map of language codes to their names for clearer instructions
        language_names = {
            "en": "English",
            "fr": "French (Français)",
            "es": "Spanish (Español)",
            "zh": "Chinese (中文)",
            "hi": "Hindi (हिंदी)"
        }

        # Define language-specific extraction instructions
        extraction_system_prompt = "You are a data extraction specialist for immigration applications."
        if language and language != "en":
            language_name = language_names.get(language, language)
            extraction_system_prompt += f"""
                The user's conversation is in {language_name}. 
                Extract information accurately while understanding content in {language_name}.
                Return the extracted data in standard field names in English for system compatibility.
            """
        
        # Format messages for Cohere
        cohere_messages = []
        for msg in messages:
            role = msg["role"]
            # Map roles to Cohere's format
            if role == "user":
                cohere_role = "USER"
            elif role == "assistant":
                cohere_role = "CHATBOT"
            else:
                continue
            
            cohere_messages.append({
                "role": cohere_role,
                "message": msg["content"]
            })
        
        # Add extraction request as the final message
        extraction_message = {
            "role": "USER",
            "message": extraction_prompt
        }

        response = client.chat(
            model=MODEL,
            message=extraction_message["message"],
            chat_history=cohere_messages,
            temperature=0.2,  # Lower temperature for more deterministic responses
            preamble=extraction_system_prompt,
            max_tokens=1000,
        )

        # Extract the JSON from the response
        try:
            response_text = response.text if hasattr(response, 'text') else str(response)
            
            # First, try to extract a JSON block if it exists
            json_match = re.search(r'```json\n([\s\S]*?)\n```|{[\s\S]*?}', response_text)
            
            if json_match:
                json_str = json_match.group(1) or json_match.group(0)
                return json.loads(json_str)
            
            # If no JSON block, try to parse the whole response
            return json.loads(response_text)
        except Exception as error:
            print(f"Failed to parse extracted form data: {error}")
            return {}
    except Exception as error:
        print(f"Error extracting form data: {error}")
        # Return an empty object when we can't extract data
        return {}

async def validate_form_data(
    form_data: Dict[str, Any],
    language: str = "en"
) -> Dict[str, Any]:
    """Validate form data and identify issues."""
    try:
        validation_prompt = f"""
            Validate the following study permit application data for completeness and potential issues:
            {json.dumps(form_data, indent=2)}
            
            Check for:
            - Missing required fields
            - Inconsistencies in dates or information
            - Potential immigration red flags
            - Format issues in identification numbers or dates
            
            Return ONLY a JSON response with format: {{ "valid": boolean, "issues": string[] }}
            Do not include any additional text, just the JSON object.
        """

        # Map of language codes to their names for clearer instructions
        language_names = {
            "en": "English",
            "fr": "French (Français)",
            "es": "Spanish (Español)",
            "zh": "Chinese (中文)",
            "hi": "Hindi (हिंदी)"
        }

        # Define language-specific validation instructions
        validation_system_prompt = "You are a data validation expert for immigration applications."
        if language and language != "en":
            language_name = language_names.get(language, language)
            validation_system_prompt += f"""
                The user prefers communication in {language_name}. 
                Provide all validation messages and feedback in {language_name}.
            """

        response = client.chat(
            model=MODEL,
            message=validation_prompt,
            temperature=0.2,  # Lower temperature for more deterministic responses
            preamble=validation_system_prompt,
            max_tokens=1000,
        )

        try:
            response_text = response.text if hasattr(response, 'text') else str(response)
            
            # First, try to extract a JSON block if it exists
            json_match = re.search(r'```json\n([\s\S]*?)\n```|{[\s\S]*?}', response_text)
            
            if json_match:
                json_str = json_match.group(1) or json_match.group(0)
                return json.loads(json_str)
            
            # If no JSON block, try to parse the whole response
            return json.loads(response_text)
        except Exception as error:
            print(f"Failed to parse validation result: {error}")
            return {"valid": False, "issues": ["Error validating form data"]}
    except Exception as error:
        print(f"Error validating form data: {error}")
        
        # Simple validation logic when Cohere is unavailable
        issues = []
        
        # Check for empty or incomplete personal information
        if "personalInfo" not in form_data or len(form_data.get("personalInfo", {})) < 3:
            issues.append("Personal information is incomplete.")
        
        # Check for education details for study permit
        if "education" not in form_data or "canadianEducation" not in form_data.get("education", {}):
            issues.append("Education information is missing or incomplete.")
        
        # If no issues were found but data is very minimal, add a general notice
        if len(issues) == 0 and len(form_data) < 3:
            issues.append("Application information appears incomplete. Please provide more details.")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues if len(issues) > 0 else ["Unable to perform full validation due to technical issues. Basic validation shows no critical issues."]
        }

# Main terminal-based interview function
async def immigration_interview():
    """Run the immigration assistant interview process in the terminal."""
    print("\033[1m" + "=" * 80 + "\033[0m")
    print("\033[1m🍁 Canadian Immigration Assistant 🍁\033[0m")
    print("\033[1m" + "=" * 80 + "\033[0m")
    print("\nWelcome to the Canadian Immigration Assistant. I'll help guide you through the application process.")
    print("Type 'exit' at any time to quit, 'show summary' to see your progress, or 'start over' to restart.\n")
    
    # Initialize conversation
    messages = []
    collected_data = {}
    language = "en"  # Default language
    
    # Initial system message
    messages.append({
        "role": "assistant", 
        "content": "Hello! I'm your Canadian Immigration Assistant. I'll help you with your work permit application. Let's start with some basic personal information. What's your full name?"
    })
    print("\033[94m" + messages[-1]["content"] + "\033[0m")
    
    while True:
        # Get user input
        user_input = input("\n\033[92mYou: \033[0m").strip()
        
        # Check for exit command
        if user_input.lower() == "exit":
            print("\nThank you for using the Canadian Immigration Assistant. Goodbye!")
            break
        
        # Check for summary command
        if user_input.lower() == "show summary":
            print("\n\033[93m" + "=" * 60 + "\033[0m")
            print("\033[93mApplication Summary\033[0m")
            print("\033[93m" + "=" * 60 + "\033[0m")
            
            # Extract data from conversation
            summary_data = await extract_form_data(messages)
            
            # Display summary
            if summary_data:
                print(json.dumps(summary_data, indent=2))
            else:
                print("No information collected yet.")
            
            print("\033[93m" + "=" * 60 + "\033[0m")
            continue
        
        # Check for restart command
        if user_input.lower() == "start over":
            messages = []
            collected_data = {}
            messages.append({
                "role": "assistant", 
                "content": "Let's start over with your application. What's your full name?"
            })
            print("\n\033[94m" + messages[-1]["content"] + "\033[0m")
            continue
        
        # Add user message to history
        messages.append({
            "role": "user", 
            "content": user_input
        })
        
        # Generate AI response
        response = await generate_chat_response(messages, collected_data, language)
        
        # Process the response
        if "collectedData" in response:
            # Update collected data
            for key, value in response["collectedData"].items():
                if isinstance(value, dict) and key in collected_data and isinstance(collected_data[key], dict):
                    collected_data[key].update(value)
                else:
                    collected_data[key] = value
        
        # Add assistant response to history
        messages.append({
            "role": "assistant", 
            "content": response["message"]
        })
        
        # Handle special actions
        if "action" in response:
            if response["action"] == "showFormPreview":
                print("\n\033[93m" + "=" * 60 + "\033[0m")
                print("\033[93mForm Preview\033[0m")
                print("\033[93m" + "=" * 60 + "\033[0m")
                
                if "formPreview" in response:
                    form_preview = response["formPreview"]
                    print(f"Title: {form_preview.get('title', 'Application Form')}")
                    
                    for section in form_preview.get("sections", []):
                        print(f"\n[{section.get('label', 'Section')}]")
                        for key, value in section.get("data", {}).items():
                            print(f"  {key}: {value}")
                else:
                    print("Form preview not available.")
                
                print("\033[93m" + "=" * 60 + "\033[0m\n")
        
        # Display assistant response
        print("\n\033[94mAssistant: " + response["message"] + "\033[0m")
        
        # Check if language detection is needed
        # Simple detection based on first few characters
        if not user_input.isascii() or any(word in user_input.lower() for word in ["français", "español", "中文", "हिंदी"]):
            # Attempt to detect language from user input
            if "français" in user_input.lower():
                language = "fr"
            elif "español" in user_input.lower():
                language = "es"
            elif "中文" in user_input:
                language = "zh"
            elif "हिंदी" in user_input:
                language = "hi"

# Main entry point
if __name__ == "__main__":
    import asyncio
    asyncio.run(immigration_interview())