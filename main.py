from crewai import Agent, Crew, Task
from crewai_tools import SerperDevTool
import cohere
from langchain_cohere import ChatCohere
import json
import requests
from requests.exceptions import RequestException
import os
from dotenv import load_dotenv

load_dotenv()


def agents(topic,model):

    researcher = Agent(
    role='Content Researcher',
    goal=f'Research thoroughly on topic',
    backstory='Expert content researcher with 10 years of experience in delivering comprehensive research.',
    llm=model,
    tools=[SerperDevTool()],
    verbose=True,
    max_execution_time=60,
    max_iter=3
) 
    writer = Agent(
        role='Blog Writer',
        goal='Create engaging blog content',
        backstory="""Professional blog writer specializing in Medium-style articles with engaging introductions, clear sections, and strong conclusions.
                    Always start the blog with greetings and a warm welcome to the reader.
                    Be intractive with the reader.
                    Add code or example if required""",        

        llm=model,
        verbose=True
    )

    editor = Agent(
        role='Content Editor',
        goal='Enhance and SEO-optimize content for maximum engagement',
        backstory='Experienced editor skilled in crafting interactive content and implementing SEO strategies for optimal visibility.',
        llm=model,
        verbose=True,
    )

    title_generator = Agent(
        role='Title Generator',
        goal='Generate a captivating title for the blog post',
        backstory='Expert title generator',
        llm=model,
        verbose=True,
    )

    return researcher, writer, editor, title_generator


def tasks(researcher, writer, editor, topic, title_generator, preferences):
    research_task = Task(
        description=(
            f'Conduct an in-depth, intelligent analysis on the topic "{topic}" for a high-quality blog post. '
            f'Leverage diverse data sources, including academic papers, recent news, credible blogs, and industry reports. '
            f'Focus on extracting nuanced insights, identifying gaps, and highlighting actionable trends. '
            f'Use advanced reasoning to prioritize relevant information and filter out noise. '
            f'Incorporate real-world examples, case studies, and data visualizations where applicable.'
        ),
        expected_output=(
            'A meticulously organized research document, providing: \n'
            '- Code examples and real-world applications where relevant.\n'
            'all insghts must be coverd nothing left'
            '- Categorized insights with citations and references (e.g., Introduction, Key Points, Analysis, and Conclusion).'
        ),
        agent=researcher
    )

    writer_task = Task(
        description=f'''
        Write a comprehensive and engaging blog post  with the following specifications:

    *Content Preferences*:
    - Tone or any preferences: {preferences['tone']}
    - Target Audience: {preferences['target_audience']}
    - Content Length: {preferences['content_length']}
    - Special Focus: {preferences['special_focus']}

    *Guidelines*:
    - Begin with a warm and relatable introduction that immediately connects with the reader.
    - Break down complex ideas into simple, clear explanations, ensuring accessibility for the target audience.
    - Use examples, relatable analogies, or code to make the content more interactive and engaging.
    - Organize the blog post logically with well-crafted headings and subheadings that feel authentic and relevant.
    - You must Avoid generic or AI-like phrasing in headings and body content. Make the language vibrant and creative.
    - End with a thoughtful conclusion that reflects on the topic, encourages further engagement, and leaves the reader with something to ponder.
    - Do not include AI terminology, signatures, timestamps, or references to how the content was created.
    - Add code or example or formulas in technical topics
    ''',
        expected_output='A complete, engaging, and thoughtfully written blog post draft that matches the specified preferences and target audience.',
        agent=writer,
    )

    editor_task = Task(
        description='''Enhance the blog post for maximum clarity, engagement, and SEO optimization.
        must Remove any signatures, timestamps, or metadata 
        make content natural, not robotic or ai like''',
        expected_output='Final, polished blog post optimized for publication and reader engagement.',
        agent=editor,
    )
    title_task = Task(
        description="""
                    
            Act as a highly experienced SEO strategist and professional copywriter. Your task is to generate exactly 5 unique, SEO-optimized, and engaging blog post titles for a Medium article.

            Titles should be in story, question, or opinion-based formats.
            Titles must follow SEO principles, targeting relevant keywords.
            Absolutely do not use colons (:) or similar punctuation like dashes (-), slashes (/), or semicolons (;).
            The titles must be concise, easy to read, and fit modern digital trends.

            """,
        expected_output='5 unique and SEO-optimized title for the blog post one per line',
        agent=title_generator,
    )


    crew = Crew(
        agents=[researcher, writer, editor, title_generator],
        tasks=[research_task, writer_task, editor_task, title_task],
        verbose=True
    )

    return crew

def publish_to_medium(title, content, tags=None):
    """
    Publish content to Medium using their API
    """
    try:
        medium_token = os.getenv('MEDIUM_TOKEN')
        if not medium_token:
            raise ValueError("Medium API token not found. Please add your MEDIUM_TOKEN to the .env file")

        headers = {
            'Authorization': f'Bearer {medium_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        
        try:
            user_response = requests.get(
                'https://api.medium.com/v1/me',
                headers=headers,
                timeout=10  
            )
            user_response.raise_for_status()
            user_data = user_response.json()
            if 'data' not in user_data or 'id' not in user_data['data']:
                raise ValueError("Invalid user data received from Medium API")
            user_id = user_data['data']['id']
        except requests.exceptions.Timeout:
            raise RequestException("Timeout while connecting to Medium API. Please try again.")
        except requests.exceptions.RequestException as e:
            raise RequestException(f"Failed to get user details: {str(e)}")

    
        formatted_content = content if content.startswith('# ') else f'# {title}\n\n{content}'
        if tags is None:
            tags = []
        elif isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(',')]
    
        if not tags:
            tags = ["Technology", "Programming", "Software Development"]

        tags = [tag for tag in tags if tag.strip()]  
        if len(tags) > 5: 
            tags = tags[:5]
        post_url = f'https://api.medium.com/v1/users/{user_id}/posts'
        post_data = {
            'title': title,
            'contentFormat': 'markdown',
            'content': formatted_content,
            'tags': tags,
            'publishStatus': 'draft',
            'notifyFollowers': True
        }

        try:
            response = requests.post(
                post_url,
                headers=headers,
                json=post_data,
                timeout=15 
            )
            response.raise_for_status()
            
            result = response.json()
            if 'data' not in result:
                raise ValueError("Invalid response from Medium API")
                
            return {
                'url': result['data'].get('url'),
                'title': result['data'].get('title'),
                'status': 'success',
                'message': 'Successfully published to Medium'
            }

        except requests.exceptions.Timeout:
            raise RequestException("Timeout while publishing to Medium. Please try again.")
        except requests.exceptions.RequestException as e:
            if hasattr(e.response, 'json'):
                error_data = e.response.json()
                error_msg = error_data.get('errors', [{'message': str(e)}])[0].get('message')
                raise RequestException(f"Medium API Error: {error_msg}")
            raise RequestException(f"Failed to publish to Medium: {str(e)}")

    except RequestException as e:
        print(f"Error publishing to Medium: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }
    except Exception as e:
        print(f"Unexpected error publishing to Medium: {str(e)}")
        return {
            'status': 'error',
            'message': 'An unexpected error occurred while publishing to Medium'
        }

def get_user_title_choice(title_output):
    try:
        content = str(title_output)
        titles = [line.strip().split('. ', 1)[-1].strip('"') for line in content.split('\n') 
                 if line.strip() and line[0].isdigit()]
        
        if not titles:
            print("No valid titles found. Regenerating...")
            return 'regenerate'
        
        print("\nSuggested titles:")
        for i, title in enumerate(titles, 1):
            print(f"{i}. {title}")
        
        print("\nOptions:")
        print("1-N: Choose a title")
        print("R: Regenerate titles")
        print("C: Create your own title")
        
        choice = input("\nEnter your choice: ").strip().upper()
        
        if choice == 'R':
            return 'regenerate'
        elif choice == 'C':
            custom_title = input("Enter your custom title: ").strip()
            return custom_title
        else:
            try:
                index = int(choice) - 1
                if 0 <= index < len(titles):
                    return titles[index]
                else:
                    print("Invalid number. Please try again.")
                    return get_user_title_choice(title_output)
            except ValueError:
                print("Invalid input. Please try again.")
                return get_user_title_choice(title_output)
    except Exception as e:
        print(f"Error processing titles: {str(e)}")
        return 'regenerate'
    
def generate_content(topic, title, preferences, editor_output):
    try:
        edited_content = editor_output[-2] if len(editor_output) >= 2 else None
        
        if not edited_content:
            raise ValueError("No edited content available")
            
        return {
            'content': edited_content,
            'status': 'success'
        }
    except Exception as e:
        return {
            'error': str(e),
            'status': 'error'
        }

def tag_generator(topic, title):
    try:
        co = cohere.ClientV2()
        response = co.chat(
            model="command-r-plus-08-2024",
            temperature=0.8,
            messages=[{
                "role": "user", 
                "content": f"""Generate 8 relevant tags for a Medium blog post about {topic} with the title {title}
                Requirements:
                    - Each tag should be relevant to the topic and title discussed
                    - Add most used tags and trending tags in medium platform
                    - Each tag should be on a new line
                    - Format each tag as a numbered list (1. Tag)
                    - Must be 8 tags
                    - No additional text or comments
                    - Do not include backslashes or special characters"""
            }]
        )
        
        response_text = response.message.content[0].text
        tag_lines = [line.strip() for line in response_text.split('\n') if line.strip()]
        tags_list = []
        for line in tag_lines:
            if '. ' in line:
                try:
                    tag = line.split('. ')[1].strip()
                    if tag:
                        tags_list.append(tag)
                except IndexError:
                    continue
        
        print("\nAvailable tags:")
        for i, tag in enumerate(tags_list, 1):
            print(f"{i}. {tag}")
            
        return tags_list
        
    except Exception as e:
        print(f"Error in tag_generator: {str(e)}")
        raise

def edit_content(content, user_preference, model):
    """
    Edit content based on user preferences using an AI model
    """
    editor = Agent(
        role="Content Editor",
        goal="Enhance and optimize content based on user preferences",
        backstory="""Expert content editor skilled in improving content clarity, adding examples, 
                    technical details, and making content more engaging while maintaining the original format.""",
        llm=model,
        verbose=True
    )
    
    edit_task = Task(
        description=f'''
        Enhance the following content according to this specific request: {user_preference}
        
        Guidelines:
        1. Keep the same markdown formatting (headers, lists, code blocks)
        2. Maintain the overall structure and flow
        3. Add requested improvements while preserving the original message
        5. Make the content more engaging and reader-friendly
        
        Content to edit:
        {content}
        ''',
        agent=editor,
        expected_output='Enhanced version of the content with requested improvements while maintaining original format'
    )
    
    editing_crew = Crew(
        agents=[editor],
        tasks=[edit_task],
        verbose=True
    )
    
    result = editing_crew.kickoff()
    edited_content = result.tasks_output[-1]  
    if hasattr(edited_content, 'raw_output'):
        return edited_content.raw_output
    elif hasattr(edited_content, 'output'):
        return edited_content.output
    else:
        return str(edited_content)

def get_content_preferences():
    print("\nLet's customize your blog post!")
    print("\nPlease specify your preferences (press Enter to skip):")
    
    tone = input("1. Preferred tone (e.g., professional, casual, technical): ").strip()
    target_audience = input("2. Target audience (e.g., beginners, experts, general public): ").strip()
    content_length = input("3. Desired length (e.g., short, medium, long): ").strip()
    special_focus = input("4. Any specific aspects to focus on?: ").strip()
    
    preferences = {
        "tone": tone or "conversational yet professional",
        "target_audience": target_audience or "general audience with basic understanding",
        "content_length": content_length or "medium",
        "special_focus": special_focus or "general overview"
    }
    
    return preferences

def create_writer_task(topic, preferences, writer):
    writer_task = Task(
        description=f'''
        Write a comprehensive and engaging blog post on the topic "{topic}" with the following specifications:

    *Content Preferences*:
    - Tone: {preferences['tone']}
    - Target Audience: {preferences['target_audience']}
    - Content Length: {preferences['content_length']}
    - Special Focus: {preferences['special_focus']}

    *Guidelines*:
    - Begin with a warm and relatable introduction that immediately connects with the reader.
    - Break down complex ideas into simple, clear explanations, ensuring accessibility for the target audience.
    - Use examples, relatable analogies, or practical insights to make the content more interactive and engaging.
    - Organize the blog post logically with well-crafted headings and subheadings that feel authentic and relevant.
    - Avoid generic or AI-like phrasing in headings and body content. Make the language vibrant and creative.
    - Maintain the specified tone throughout, keeping the reader interested and inspired.
    - End with a thoughtful conclusion that reflects on the topic, encourages further engagement, and leaves the reader with something to ponder.
    - Do not include AI terminology, signatures, timestamps, or references to how the content was created.
    ''',
        expected_output='A complete, engaging, and thoughtfully written blog post draft that matches the specified preferences and target audience.',
        agent=writer,
    )
    return writer_task

def main():
    model = ChatCohere(model="command-r-plus", streaming=True, temperature=0.6)
    topic = input("Please enter the topic for the blog post: ")
    preferences = get_content_preferences()
        
    researcher, writer, editor, title_generator = agents(topic, model)

    writer_task = create_writer_task(topic, preferences, writer)
    
    crew = tasks(researcher, writer, editor, topic, title_generator, preferences)

    try:
        crew_output = crew.kickoff()
        while True:
            title_output = crew_output.tasks_output[-1]
            title_choice = get_user_title_choice(title_output)
            if title_choice == 'regenerate':
                continue
            elif title_choice not in ['1', '2', '3', '4', '5']:
                blog_title = title_choice
                break
            else:
                titles = title_output.message.content[0].text.split('\n')
                blog_title = titles[int(title_choice) - 1]
                break
        
        blog_content = generate_content(topic, blog_title, preferences, crew_output.tasks_output)
        
        user_preference = input("Please enter your preference for the content: ").strip()
        
        regenerate_choice = input("Would you like to edit the content? (y/n): ").strip().lower()
        if regenerate_choice == 'y':
            edited_response = edit_content(blog_content['content'], user_preference)
            blog_content = edited_response
        
        tags_list = tag_generator(topic, blog_title)
        
        if not tags_list:
            print("No tags were generated. Using default tags.")
            tags_list = ["Technology", "Programming", "Software Development", "Tech", "Coding"]
        
        print("\nSelect 5 tags from the following options:")
        for i, tag in enumerate(tags_list, 1):
            print(f"{i}. {tag}")
        
        while True:
            try:
                selections = input("\nEnter 5 numbers separated by commas (e.g., 1,2,3,4,5): ").strip()
                selected_indices = [int(x.strip()) - 1 for x in selections.split(',')]
                
                if len(selected_indices) != 5:
                    print("Please select exactly 5 tags.")
                    continue
                    
                if any(i < 0 or i >= len(tags_list) for i in selected_indices):
                    print("Invalid selection. Please choose from available numbers.")
                    continue
                    
                tags = [tags_list[i] for i in selected_indices]
                print("\nSelected tags:", tags)
                break
            except ValueError:
                print("Invalid input. Please enter numbers separated by commas.")
        
        print("\nPublishing to Medium...")
        result = publish_to_medium(blog_title, blog_content['content'], tags)
        
        if result:
            print(f"Successfully published to Medium! Post URL: {result.get('data', {}).get('url', 'URL not available')}")
        else:
            print("Failed to publish to Medium. Saving content locally...")
            with open('blog_post.md', 'w', encoding='utf-8') as f:
                f.write(f"# {blog_title}\n\n{blog_content}")
            print("Content saved to blog_post.md")
        
        print("\nTask Outputs:")
        for i, output in enumerate(crew_output.tasks_output):
            print(f"\nTask {i+1}:")
            print(output)
            
        print(f"\nToken Usage: {crew_output.token_usage}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        try:
            with open('blog_post_backup.md', 'w', encoding='utf-8') as f:
                f.write(f"# {blog_title}\n\n{blog_content}")
            print("Content saved to blog_post_backup.md")
        except:
            print("Could not save backup file")

if __name__ == "__main__":
    main()