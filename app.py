"""
ComicForge 漫鍛 — AI Comic Generator
Upload character ref + input story → generate consistent comic panels
"""
import os, uuid, hashlib, base64, io, json
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file, abort
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "comicforge-dev")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///comicforge.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "output")
app.config["CHAR_FOLDER"] = os.path.join(os.path.dirname(__file__), "characters")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["CHAR_FOLDER"], exist_ok=True)

CORS(app)
db = SQLAlchemy(app)

# ========== Art Styles ==========
ART_STYLES = [
    {"id": "manga_bw",    "name": "日系黑白漫畫",  "prompt": "black and white manga, screentones, sharp ink lines, dynamic composition, manga panel layout", "icon": "fa-book", "preview": "📖"},
    {"id": "manga_color", "name": "日系彩色漫畫",  "prompt": "color manga, anime style, cel shading, vibrant colors, detailed backgrounds, manga panel", "icon": "fa-palette", "preview": "🎨"},
    {"id": "webtoon",     "name": "Webtoon 風格",  "prompt": "korean webtoon style, soft shading, pastel colors, vertical scroll format, clean lines", "icon": "fa-mobile-screen", "preview": "📱"},
    {"id": "comic_west",  "name": "美式漫畫",      "prompt": "american comic book style, bold lines, halftone dots, dramatic lighting, superhero aesthetic", "icon": "fa-bolt", "preview": "💥"},
    {"id": "watercolor",  "name": "水彩繪本",      "prompt": "watercolor illustration, soft edges, dreamy atmosphere, children book style, gentle colors", "icon": "fa-droplet", "preview": "💧"},
    {"id": "chibi",       "name": "Q版可愛",       "prompt": "chibi style, cute characters, big heads, simple expressions, kawaii aesthetic, pastel", "icon": "fa-face-smile", "preview": "😊"},
]

# ========== Models ==========
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), default="")
    password_hash = db.Column(db.String(255), nullable=False)
    plan = db.Column(db.String(50), default="free")
    panels_used = db.Column(db.Integer, default=0)
    panels_limit = db.Column(db.Integer, default=20)  # Free: 20 panels
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def can_generate(self): return self.panels_used < self.panels_limit
    def limit_info(self): return {"plan":self.plan,"used":self.panels_used,"limit":self.panels_limit,"remaining":max(0,self.panels_limit-self.panels_used)}

class Character(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    name = db.Column(db.String(255))
    ref_image = db.Column(db.String(255))  # path to reference image
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ComicProject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    title = db.Column(db.String(255))
    style = db.Column(db.String(100))
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=True)
    panels_json = db.Column(db.Text, default="[]")  # JSON array of panel descriptions
    status = db.Column(db.String(50), default="draft")
    progress = db.Column(db.Integer, default=0)  # 0-100 percentage
    total_panels = db.Column(db.Integer, default=0)
    completed_panels = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Panel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("comic_project.id"))
    panel_num = db.Column(db.Integer)
    description = db.Column(db.Text)
    dialogue = db.Column(db.Text, default="")
    output_file = db.Column(db.String(255))
    status = db.Column(db.String(50), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ========== Auth ==========
def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def d(*a, **k):
        if "user_id" not in session: return redirect(url_for("login_page"))
        return f(*a, **k)
    return d

def current_user():
    return db.session.get(User, session["user_id"]) if "user_id" in session else None

# ========== Routes ==========
@app.route("/")
def index():
    return render_template("index.html", styles=ART_STYLES)

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/app")
@login_required
def app_page():
    u = current_user()
    chars = Character.query.filter_by(user_id=u.id).all()
    return render_template("app.html", user=u, styles=ART_STYLES, characters=chars)

@app.route("/dashboard")
@login_required
def dashboard():
    u = current_user()
    projects = ComicProject.query.filter_by(user_id=u.id).order_by(ComicProject.created_at.desc()).limit(12).all()
    return render_template("dashboard.html", user=u, projects=projects)

@app.route("/health")
def health(): return jsonify({"ok":True,"service":"comicforge"})

# ========== Auth API ==========
@app.route("/api/register", methods=["POST"])
def register():
    d = request.get_json()
    email = d.get("email","").strip().lower()
    pw = d.get("password","")
    if not email or not pw: return jsonify({"error":"需要 email 和密碼"}), 400
    if User.query.filter_by(email=email).first(): return jsonify({"error":"此 email 已註冊"}), 400
    u = User(email=email, name=d.get("name",""), password_hash=hash_pw(pw))
    db.session.add(u); db.session.commit()
    session["user_id"] = u.id
    return jsonify({"success":True,"redirect":"/app"})

@app.route("/api/login", methods=["POST"])
def login():
    d = request.get_json()
    u = User.query.filter_by(email=d.get("email","").strip().lower()).first()
    if not u or u.password_hash != hash_pw(d.get("password","")): return jsonify({"error":"帳號或密碼錯誤"}), 401
    session["user_id"] = u.id
    return jsonify({"success":True,"redirect":"/app"})

@app.route("/api/logout")
def logout(): session.clear(); return redirect(url_for("index"))

# ========== Character Management ==========
@app.route("/api/character/upload", methods=["POST"])
@login_required
def upload_character():
    u = current_user()
    if "image" not in request.files: return jsonify({"error":"請上傳角色參考圖"}), 400
    name = request.form.get("name","角色")
    photo = request.files["image"]
    char_id = str(uuid.uuid4())[:8]
    ext = photo.filename.rsplit(".",1)[-1] if "." in photo.filename else "png"
    filename = f"char_{char_id}.{ext}"
    filepath = os.path.join(app.config["CHAR_FOLDER"], filename)
    photo.save(filepath)

    char = Character(user_id=u.id, name=name, ref_image=filename)
    db.session.add(char); db.session.commit()
    return jsonify({"success":True,"id":char.id,"name":char.name,"image":f"/api/character/image/{filename}"})

@app.route("/api/character/image/<filename>")
def serve_character(filename):
    path = os.path.join(app.config["CHAR_FOLDER"], filename)
    return send_file(path) if os.path.exists(path) else abort(404)

@app.route("/api/characters")
@login_required
def list_characters():
    u = current_user()
    chars = Character.query.filter_by(user_id=u.id).all()
    return jsonify([{"id":c.id,"name":c.name,"image":f"/api/character/image/{c.ref_image}"} for c in chars])

# ========== Comic Generation ==========
@app.route("/api/comic/create", methods=["POST"])
@login_required
def create_comic():
    u = current_user()
    d = request.get_json()

    title = d.get("title","我的漫畫")
    style_id = d.get("style","manga_color")
    character_id = d.get("character_id")
    panels_desc = d.get("panels",[])  # [{description: "...", dialogue: "..."}, ...]

    if not panels_desc: return jsonify({"error":"請輸入至少一格漫畫描述"}), 400
    panels_needed = len(panels_desc)
    if u.panels_used + panels_needed > u.panels_limit:
        return jsonify({"error":f"額度不足！需要 {panels_needed} 格，剩餘 {u.panels_limit - u.panels_used} 格","limit_info":u.limit_info()}), 402

    proj = ComicProject(
        user_id=u.id, title=title, style=style_id,
        character_id=character_id,
        panels_json=json.dumps(panels_desc, ensure_ascii=False),
        status="generating",
        total_panels=panels_needed,
        completed_panels=0,
        progress=0
    )
    db.session.add(proj); db.session.commit()

    # Create panel records
    for i, pd in enumerate(panels_desc):
        p = Panel(project_id=proj.id, panel_num=i+1, description=pd.get("description",""), dialogue=pd.get("dialogue",""))
        db.session.add(p)
    db.session.commit()

    # Generate panels (sync for MVP)
    style = next((s for s in ART_STYLES if s["id"]==style_id), ART_STYLES[0])
    char = db.session.get(Character, character_id) if character_id else None

    try:
        generate_all_panels(proj.id, style, char)
        u.panels_used += panels_needed
        proj.status = "done"
        proj.progress = 100
        proj.completed_panels = panels_needed
        db.session.commit()
        return jsonify({"success":True,"id":proj.id,"panels":panels_needed,"limit_info":u.limit_info()})
    except Exception as e:
        proj.status = "error"; db.session.commit()
        return jsonify({"error":str(e)}), 500


def generate_all_panels(project_id, style, character):
    """Generate all panels for a comic project with IP-Adapter for character consistency"""
    import torch
    from PIL import Image, ImageDraw, ImageFont
    from diffusers import StableDiffusionPipeline, StableDiffusionImg2ImgPipeline

    panels = Panel.query.filter_by(project_id=project_id).order_by(Panel.panel_num).all()
    proj = db.session.get(ComicProject, project_id)
    total_panels = len(panels)

    # Load pipeline (lazy)
    if not hasattr(app, "_sd_pipe"):
        print("[ComicForge] Loading SD pipeline...")
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        app._sd_pipe = StableDiffusionPipeline.from_pretrained(
            "runwayml/stable-diffusion-v1-5",
            torch_dtype=torch.float16 if device == "mps" else torch.float32,
            safety_checker=None,
        ).to(device)
        app._sd_pipe.enable_attention_slicing()
        print(f"[ComicForge] SD loaded on {device}")

    pipe = app._sd_pipe

    # Character reference (if provided)
    char_image = None
    char_image_path = None
    if character and character.ref_image:
        char_path = os.path.join(app.config["CHAR_FOLDER"], character.ref_image)
        if os.path.exists(char_path):
            char_image = Image.open(char_path).convert("RGB").resize((512,512))
            char_image_path = char_path

    for i, panel in enumerate(panels):
        print(f"[ComicForge] Generating panel {panel.panel_num} ({i+1}/{total_panels})...")

        prompt = f"{style['prompt']}, {panel.description}, single comic panel, professional illustration, high quality"
        negative = "blurry, low quality, deformed, ugly, extra limbs, bad anatomy, watermark, text, multiple panels"

        # If we have a character reference, use IP-Adapter for better consistency
        if char_image_path:
            try:
                # Try to use IP-Adapter for character consistency
                from ip_adapter import IPAdapter, IPAdapterXL
                from ip_adapter.utils import register_cross_attention_hook
                
                # Load IP-Adapter model if not loaded
                if not hasattr(app, "_ip_adapter"):
                    print("[ComicForge] Loading IP-Adapter...")
                    app._ip_adapter = IPAdapter(
                        app._sd_pipe,
                        "ip-adapter_sd15.bin",  # Download from https://huggingface.co/h94/IP-Adapter
                        device="mps" if torch.backends.mps.is_available() else "cpu",
                    )
                
                # Use IP-Adapter with character reference
                result = app._ip_adapter.generate(
                    prompt=prompt,
                    negative_prompt=negative,
                    pil_image=char_image,
                    scale=0.8,  # Character influence strength
                    width=512,
                    height=512,
                    num_inference_steps=25,
                    guidance_scale=7.5,
                )
                img = result.images[0]
                print(f"[ComicForge] Used IP-Adapter for panel {panel.panel_num}")
            except ImportError:
                print("[ComicForge] IP-Adapter not available, falling back to img2img")
                # Fallback to img2img if IP-Adapter not installed
                if not hasattr(app, "_img2img_pipe"):
                    from diffusers import StableDiffusionImg2ImgPipeline
                    app._img2img_pipe = StableDiffusionImg2ImgPipeline.from_pretrained(
                        "runwayml/stable-diffusion-v1-5",
                        torch_dtype=torch.float16 if torch.backends.mps.is_available() else torch.float32,
                        safety_checker=None,
                    ).to("mps" if torch.backends.mps.is_available() else "cpu")
                    app._img2img_pipe.enable_attention_slicing()

                result = app._img2img_pipe(
                    prompt=prompt, negative_prompt=negative,
                    image=char_image, strength=0.7,
                    guidance_scale=7.5, num_inference_steps=25,
                )
                img = result.images[0]
            except Exception as e:
                print(f"[ComicForge] IP-Adapter error: {e}, falling back to img2img")
                # Fallback to img2img on any error
                if not hasattr(app, "_img2img_pipe"):
                    from diffusers import StableDiffusionImg2ImgPipeline
                    app._img2img_pipe = StableDiffusionImg2ImgPipeline.from_pretrained(
                        "runwayml/stable-diffusion-v1-5",
                        torch_dtype=torch.float16 if torch.backends.mps.is_available() else torch.float32,
                        safety_checker=None,
                    ).to("mps" if torch.backends.mps.is_available() else "cpu")
                    app._img2img_pipe.enable_attention_slicing()

                result = app._img2img_pipe(
                    prompt=prompt, negative_prompt=negative,
                    image=char_image, strength=0.7,
                    guidance_scale=7.5, num_inference_steps=25,
                )
                img = result.images[0]
        else:
            # No character reference, use regular generation
            result = pipe(
                prompt=prompt, negative_prompt=negative,
                width=512, height=512,
                guidance_scale=7.5, num_inference_steps=25,
            )
            img = result.images[0]

        # Add dialogue bubble if needed
        if panel.dialogue:
            img = add_dialogue_bubble(img, panel.dialogue)

        # Save
        filename = f"panel_{project_id}_{panel.panel_num}.png"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        img.save(filepath)

        panel.output_file = filename
        panel.status = "done"
        
        # Update progress
        proj.completed_panels = i + 1
        proj.progress = int((i + 1) / total_panels * 100)
        db.session.commit()
        
        print(f"[ComicForge] Panel {panel.panel_num} completed. Progress: {proj.progress}%")


def add_dialogue_bubble(img, text, position="top-right"):
    """Add a professional speech bubble to a comic panel"""
    from PIL import ImageDraw, ImageFont, ImageFilter
    import textwrap
    
    draw = ImageDraw.Draw(img)
    w, h = img.size
    
    # Calculate bubble dimensions based on text length
    try:
        font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 14)
    except:
        font = ImageFont.load_default()
    
    # Wrap text to fit in bubble
    wrapper = textwrap.TextWrapper(width=15)
    lines = wrapper.wrap(text)
    lines = lines[:3]  # Limit to 3 lines
    
    # Calculate text dimensions
    text_width = 0
    text_height = 0
    for line in lines:
        bbox = font.getbbox(line)
        line_width = bbox[2] - bbox[0]
        line_height = bbox[3] - bbox[1]
        text_width = max(text_width, line_width)
        text_height += line_height + 4
    
    # Add padding
    padding = 12
    bubble_width = text_width + padding * 2
    bubble_height = text_height + padding * 2
    
    # Position bubble
    if position == "top-right":
        bubble_x = w - bubble_width - 20
        bubble_y = 20
    elif position == "top-left":
        bubble_x = 20
        bubble_y = 20
    elif position == "bottom-right":
        bubble_x = w - bubble_width - 20
        bubble_y = h - bubble_height - 20
    elif position == "bottom-left":
        bubble_x = 20
        bubble_y = h - bubble_height - 20
    else:  # center
        bubble_x = (w - bubble_width) // 2
        bubble_y = 20
    
    # Draw shadow
    shadow_offset = 3
    draw.rounded_rectangle(
        [bubble_x + shadow_offset, bubble_y + shadow_offset, 
         bubble_x + bubble_width + shadow_offset, bubble_y + bubble_height + shadow_offset],
        radius=12, fill=(0, 0, 0, 100)
    )
    
    # Draw bubble
    draw.rounded_rectangle(
        [bubble_x, bubble_y, bubble_x + bubble_width, bubble_y + bubble_height],
        radius=12, fill="white", outline="black", width=2
    )
    
    # Draw text
    y_offset = bubble_y + padding
    for line in lines:
        draw.text((bubble_x + padding, y_offset), line, fill="black", font=font)
        bbox = font.getbbox(line)
        y_offset += (bbox[3] - bbox[1]) + 4
    
    # Draw tail (pointing to bottom-right for top-right bubble)
    if position == "top-right":
        tail_points = [
            (bubble_x + bubble_width - 30, bubble_y + bubble_height),
            (bubble_x + bubble_width - 10, bubble_y + bubble_height + 15),
            (bubble_x + bubble_width - 40, bubble_y + bubble_height)
        ]
    elif position == "top-left":
        tail_points = [
            (bubble_x + 30, bubble_y + bubble_height),
            (bubble_x + 10, bubble_y + bubble_height + 15),
            (bubble_x + 40, bubble_y + bubble_height)
        ]
    else:
        # Default tail for other positions
        tail_points = [
            (bubble_x + 30, bubble_y + bubble_height),
            (bubble_x + 50, bubble_y + bubble_height + 15),
            (bubble_x + 60, bubble_y + bubble_height)
        ]
    
    draw.polygon(tail_points, fill="white", outline="black")
    
    return img


# ========== Get Comic ==========
@app.route("/api/comic/<int:proj_id>")
@login_required
def get_comic(proj_id):
    u = current_user()
    proj = db.session.get(ComicProject, proj_id)
    if not proj or proj.user_id != u.id: return jsonify({"error":"找不到"}), 404
    panels = Panel.query.filter_by(project_id=proj_id).order_by(Panel.panel_num).all()
    return jsonify({
        "id": proj.id, "title": proj.title, "style": proj.style,
        "status": proj.status,
        "progress": proj.progress,
        "total_panels": proj.total_panels,
        "completed_panels": proj.completed_panels,
        "panels": [{
            "num": p.panel_num, "description": p.description,
            "dialogue": p.dialogue, "status": p.status,
            "url": f"/api/image/{p.output_file}" if p.output_file else None
        } for p in panels]
    })

@app.route("/api/image/<filename>")
def serve_image(filename):
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    return send_file(path) if os.path.exists(path) else abort(404)

# ========== Me / History ==========
@app.route("/api/me")
@login_required
def me():
    u = current_user()
    return jsonify({"email":u.email,"name":u.name,"plan":u.plan,"limit_info":u.limit_info()})

@app.route("/api/projects")
@login_required
def list_projects():
    u = current_user()
    projs = ComicProject.query.filter_by(user_id=u.id).order_by(ComicProject.created_at.desc()).all()
    return jsonify([{
        "id": p.id,
        "title": p.title,
        "style": p.style,
        "status": p.status,
        "progress": p.progress,
        "total_panels": p.total_panels,
        "completed_panels": p.completed_panels,
        "panels": len(json.loads(p.panels_json)),
        "created": p.created_at.isoformat()
    } for p in projs])

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5003))
    print(f"[ComicForge] http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
