import os
import openai
import base64
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from reportlab.lib.pagesizes import A5, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import Color
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph
from io import BytesIO
from fastapi.responses import StreamingResponse

# --- OpenAI Client Setup ---
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("WARNING: OPENAI_API_KEY environment variable not set.")
client = openai.AsyncOpenAI(api_key=api_key)

# --- FastAPI App Setup ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class StoryRequest(BaseModel):
    theme: str

class BookRequest(BaseModel):
    title: str
    paragraphs: List[str]

# --- Prompts for AI ---
ART_STYLE_PROMPT = """
**Art Style:** A high-quality digital painting in the style of a classic children's book with a gentle, pictorial, and artisanal watercolor finish. The lighting must be warm and soft, creating a cozy and nostalgic atmosphere. All images must be in a 4:3 landscape aspect ratio.

**Character Descriptions (Mandatory):**
*   **Pepito:** A 3-year-old boy, small in stature, with messy dark brown hair, big brown eyes, and rosy cheeks. He is always wearing the exact same outfit: a sweater with horizontal red and orange stripes, and blue shorts. He has fair skin.
*   **Pepón:** A 5-year-old boy, taller and sturdier than his brother, with neat dark brown hair. He is always wearing the exact same outfit: a blue and yellow polo shirt (remera tipo chomba) and dark long pants. He has the same fair skin as his brother.

**Consistency Rule:** Pepito and Pepón must look identical in every single image, with the exact same face, hair, and clothing as described.
"""

# --- Helper Functions ---
async def generate_image_data(prompt: str) -> bytes:
    """Generates an image using DALL-E 3 and returns its base64 decoded data."""
    full_prompt = f"{ART_STYLE_PROMPT}\n\n**Scene:** {prompt}"
    try:
        response = await client.images.generate(
            model="dall-e-3",
            prompt=full_prompt,
            size="1024x768",  # 4:3 aspect ratio
            quality="standard",
            n=1,
            response_format="b64_json",
        )
        b64_data = response.data[0].b64_json
        return base64.b64decode(b64_data)
    except Exception as e:
        print(f"Error generating image: {e}")
        # Return a placeholder or raise an exception
        raise HTTPException(status_code=500, detail=f"Failed to generate image for prompt: {prompt}")


def create_pdf_book(title: str, paragraphs: List[str], image_data: List[bytes]) -> BytesIO:
    """Creates the PDF book from story and image data."""
    buffer = BytesIO()
    p_width, p_height = landscape(A5)
    c = canvas.Canvas(buffer, pagesize=landscape(A5))

    # Page 1: Cover
    cover_image = ImageReader(BytesIO(image_data[0]))
    c.drawImage(cover_image, 0, 0, width=p_width, height=p_height, preserveAspectRatio=True, anchor='c')
    c.setFont("Helvetica-Bold", 36)
    c.setFillColorRGB(1, 1, 1, 0.9) # White, slightly transparent
    c.drawCentredString(p_width / 2.0, p_height / 4.0, title)
    c.showPage()

    # Subsequent Pages
    styles = getSampleStyleSheet()
    cream_color = Color(0.99, 0.98, 0.88) # A nice cream color
    text_style = ParagraphStyle(
        'normal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=14,
        leading=20,
        firstLineIndent=20,
        spaceAfter=12,
    )

    for i, paragraph_text in enumerate(paragraphs):
        # Text Page
        c.setFillColor(cream_color)
        c.rect(0, 0, p_width, p_height, fill=1, stroke=0)
        p = Paragraph(paragraph_text, text_style)
        p.wrapOn(c, p_width - 100, p_height - 100)
        p.drawOn(c, 50, p_height - 100)
        c.showPage()

        # Illustration Page
        scene_image = ImageReader(BytesIO(image_data[i + 1]))
        c.drawImage(scene_image, 0, 0, width=p_width, height=p_height, preserveAspectRatio=True, anchor='c')
        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer

# --- API Endpoints ---
@app.get("/")
def read_root():
    return {"message": "La Fábrica de Cuentos API is running."}

@app.post("/api/generate-story")
async def generate_story(request: StoryRequest):
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured on the server.")

    system_prompt = """
    You are a creative storyteller for children. Your task is to write a short, magical story in Spanish.

    **Rules:**
    1. The story must be exactly 5 paragraphs long.
    2. The language must be Argentinian Spanish. Use local vocabulary and phrasing naturally (e.g., "vos" instead of "tú", words like "pileta", "vereda", "barrilete" when appropriate).
    3. The main characters are two brothers, Pepito (3 years old) and Pepón (5 years old). The story must be about them.
    4. **Crucial Safety Rule:** The story can have a small, easily resolved problem or moment of tension, but it is absolutely forbidden for any character to get hurt, be in real danger, or experience significant fear. The tone must always be warm, safe, and reassuring.
    5. The story must have a clear title.
    6. Your output must be a JSON object with two keys: "title" (a string) and "paragraphs" (an array of 5 strings). Do not add any extra text or explanations outside of the JSON object.
    """

    user_prompt = f"The theme of the story is: {request.theme}"

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        # The response is a JSON string, so we can return it directly.
        # FastAPI will handle parsing it and sending it as a JSON response.
        return response.choices[0].message.content
    except Exception as e:
        print(f"An error occurred with the OpenAI API: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate story. Error: {str(e)}")


@app.post("/api/generate-book")
async def generate_book(request: BookRequest):
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured on the server.")

    # Create prompts for all 6 images
    cover_prompt = "A beautiful and attractive cover scene with the two protagonists, Pepito and Pepón, in a pleasant and safe natural landscape like a sunny meadow or a gentle forest. No text."
    scene_prompts = [cover_prompt] + request.paragraphs

    try:
        # Generate all images concurrently
        image_tasks = [generate_image_data(prompt) for prompt in scene_prompts]
        image_data_list = await asyncio.gather(*image_tasks)

        # Create the PDF
        pdf_buffer = create_pdf_book(request.title, request.paragraphs, image_data_list)

        # Return the PDF as a streaming response
        return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={
            "Content-Disposition": "attachment; filename=libro_de_cuentos.pdf"
        })

    except HTTPException as e:
        # Re-raise HTTP exceptions from helpers
        raise e
    except Exception as e:
        print(f"An error occurred during book generation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate the book. Error: {str(e)}")
