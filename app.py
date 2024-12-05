from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
from main import agents, tasks, tag_generator, publish_to_medium, edit_content
from langchain_cohere import ChatCohere
from dotenv import load_dotenv
import logging
import os
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from io import BytesIO
import re

load_dotenv()


import logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)

app = Flask(__name__)
app.config['DEBUG'] = False  

app.config['DEBUG'] = True
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


crew_output = None


DEFAULT_PREFERENCES = {
    'tone': 'professional',
    'target_audience': 'general',
    'content_length': 'medium',
    'special_focus': 'none'
}

@app.route('/')
def home():
    return render_template('main.html')

@app.route('/api/generate-titles', methods=['POST'])
def generate_titles():
    global crew_output
    try:
        data = request.get_json()
        topic = data.get('topic')
        preferences = data.get('preferences', {})

        if not topic:
            return jsonify({'error': 'Missing topic'}), 400

     
        model = ChatCohere(model="command-r-plus", streaming=True)
        researcher, writer, editor, title_generator = agents(topic, model)
        crew = tasks(researcher, writer, editor, topic, title_generator, preferences)
        crew_output = crew.kickoff()
        titles_raw = str(crew_output.tasks_output[-1])
        titles = [
            title.strip() 
            for title in titles_raw.split('\n') 
            if title.strip() and not title.strip().startswith('<!doctype')]
        
        if not titles:
            return jsonify({'error': 'No valid titles generated'}), 500

        return jsonify({
            'titles': titles,
            'status': 'success'
        })
    except Exception as e:
        logger.error(f"Error generating titles: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-content', methods=['POST'])
def generate_content_endpoint():
    global crew_output
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        if crew_output is None:
            return jsonify({'error': 'Please generate titles first'}), 400

        try:
            content = str(crew_output.tasks_output[-2])
            
            if content.lower().startswith('<!doctype') or content.lower().startswith('<html'):
                return jsonify({'error': 'Invalid content format'}), 500
            if not content or len(content.strip()) < 10:
                return jsonify({'error': 'Generated content is too short or empty'}), 500

            return jsonify({
                'content': content,
                'status': 'success'
            })
            
        except (IndexError, AttributeError) as e:
            logger.error(f"Error accessing crew output: {str(e)}")
            return jsonify({'error': 'Error accessing generated content. Please try again.'}), 500
            
        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            return jsonify({'error': 'An unexpected error occurred. Please try again.'}), 500
            
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({'error': 'Error processing request. Please try again.'}), 500

@app.route('/api/generate-tags', methods=['POST'])
def generate_tags():
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        topic = data.get('topic')
        title = data.get('title')
        
        if not topic or not title:
            return jsonify({
                'success': False,
                'message': 'Topic and title are required'
            }), 400
        
        logger.info(f"Generating tags for topic: {topic}, title: {title}")
        
        try:
            tags = tag_generator(topic, title)
            
            if not tags:
                return jsonify({
                    'success': False,
                    'message': 'No tags were generated'
                }), 500
            
            tags = tags[:8] 
            
            
            response = {
                'success': True,
                'tags': tags,
                'message': 'Tags generated successfully'
            }
            
            logger.info(f"Generated {len(tags)} tags")
            return jsonify(response)
            
        except Exception as e:
            logger.error(f"Error in tag generation: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'message': f'Tag generation failed: {str(e)}'
            }), 500
        
    except Exception as e:
        logger.error(f"Error in generate_tags endpoint: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Failed to process request: {str(e)}'
        }), 500

@app.route('/api/publish', methods=['POST'])
def publish():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        title = data.get('title')
        content = data.get('content')
        tags = data.get('tags', [])

        if not title or not content:
            return jsonify({'error': 'Title and content are required'}), 400

        if not content.startswith('# '):
            content = f'# {title}\n\n{content}'

        result = publish_to_medium(title, content, tags)
        if result is None:
            return jsonify({'error': 'Failed to publish to Medium'}), 500

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        print(f"Error publishing content: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/edit-content', methods=['POST'])
def edit_content_endpoint():
    try:
        data = request.get_json()
        content = data.get('content')
        instruction = data.get('instruction')
        
        if not content or not instruction:
            return jsonify({'error': 'Content and instruction are required'}), 400

        model = ChatCohere(cohere_api_key=os.getenv('COHERE_API_KEY'), model="command-r-plus")

        edited_content = edit_content(content, instruction, model)
        
        return jsonify({
            'content': edited_content
        })
        
    except Exception as e:
        print(f"Error editing content: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-pdf', methods=['POST'])
def download_pdf():
    try:
        data = request.get_json()
        content = data.get('content', '').strip()
        
        if not content:
            return jsonify({'error': 'No content provided'}), 400
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40,
            encoding='utf-8'
        )

        styles = getSampleStyleSheet()
    
        title_color = colors.HexColor('#000000')
        text_color = colors.HexColor('#333333')
        code_bg_color = colors.HexColor('#f5f5f5')

        def clean_text(text):
            text = re.sub(r'\s+', ' ', text).strip()
            text = text.encode('utf-8', 'ignore').decode('utf-8')
            return text

        def format_bold_text(text):
            text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
            return text

        base_style = ParagraphStyle(
            'BaseStyle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=11,
            leading=16,
            encoding='utf-8'
        )

        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=base_style,
            fontSize=11,
            leading=16,
            spaceBefore=8,
            spaceAfter=8,
            textColor=text_color
        )
        
        heading1_style = ParagraphStyle(
            'CustomHeading1',
            parent=base_style,
            fontSize=20,
            leading=24,
            spaceBefore=16,
            spaceAfter=12,
            alignment=1,
            textColor=title_color,
            fontName='Helvetica-Bold'
        )
        
        heading2_style = ParagraphStyle(
            'CustomHeading2',
            parent=base_style,
            fontSize=16,
            leading=20,
            spaceBefore=14,
            spaceAfter=10,
            textColor=title_color,
            fontName='Helvetica-Bold'
        )

        heading3_style = ParagraphStyle(
            'CustomHeading3',
            parent=base_style,
            fontSize=13,
            leading=16,
            spaceBefore=12,
            spaceAfter=8,
            textColor=title_color,
            fontName='Helvetica-Bold'
        )

        bullet_style = ParagraphStyle(
            'BulletStyle',
            parent=base_style,
            leftIndent=20,
            spaceBefore=2,
            spaceAfter=2,
            bulletIndent=10,
            textColor=text_color
        )

        code_style = ParagraphStyle(
            'CodeStyle',
            parent=base_style,
            fontName='Courier',
            fontSize=10,
            leading=12,
            textColor=text_color,
            backColor=code_bg_color,
            spaceBefore=4,
            spaceAfter=4
        )

        story = []
        story.append(Spacer(1, 8))

        try:
            from bs4 import BeautifulSoup
        
            content = format_bold_text(content)
            
            soup = BeautifulSoup(content, 'html.parser')
            
            for element in soup.find_all(['h1', 'h2', 'h3', 'p', 'ul', 'ol', 'pre', 'code', 'div', 'span', 'b']):
                if story:
                    story.append(Spacer(1, 6))
                
                if element.name == 'h1':
                    story.append(Paragraph(clean_text(element.get_text()), heading1_style))
                elif element.name == 'h2':
                    story.append(Paragraph(clean_text(element.get_text()), heading2_style))
                elif element.name == 'h3':
                    story.append(Paragraph(clean_text(element.get_text()), heading3_style))
                elif element.name in ['pre', 'code']:
                    text = clean_text(element.get_text())
                    if text:
                        story.append(Paragraph(text, code_style))
                elif element.name in ['p', 'div', 'span']:
                    text = ''
                    for content in element.contents:
                        if isinstance(content, str):
                            text += content
                        elif content.name == 'b':
                            text += f'<b>{content.get_text()}</b>'
                        elif content.name == 'code':
                            text += clean_text(content.get_text())
                        elif content.name == 'br':
                            text += '\n'
                        else:
                            text += str(content)
                    
                    text = clean_text(text)
                    if text:
                        story.append(Paragraph(text, normal_style))
                elif element.name in ['ul', 'ol']:
                    for li in element.find_all('li'):
                        bullet_text = '• ' + clean_text(li.get_text())
                        story.append(Paragraph(bullet_text, bullet_style))
            
            story.append(Spacer(1, 8))

            if not story:
                return jsonify({'error': 'No content to generate PDF'}), 400

            doc.build(story)
            buffer.seek(0)
            
            return send_file(
                buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name='blog-post.pdf'
            )

        except Exception as e:
            logger.error(f"Error parsing HTML: {str(e)}")
            return jsonify({'error': f'Error parsing HTML: {str(e)}'}), 500

    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/preferences', methods=['GET', 'POST'])
def get_preferences():
    if request.method == 'POST':
        preferences = request.get_json()
        return jsonify(preferences)
    return jsonify(DEFAULT_PREFERENCES)

if __name__ == '__main__':
    print("Starting server on http://127.0.0.1:5000")
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=True,
        use_reloader=True,
        threaded=True
    )
