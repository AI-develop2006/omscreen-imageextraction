from PIL import Image, ImageDraw, ImageFont
import os

def create_table_image(filename):
    img = Image.new('RGB', (800, 400), color = (255, 255, 255))
    d = ImageDraw.Draw(img)
    
    # Try to load a font, otherwise use default
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except IOError:
        font = ImageFont.load_default()

    text = """
    Item        | Quantity | Price
    --------------------------------
    Apples      | 5        | $2.00
    Bananas     | 12       | $3.50
    Milk        | 2        | $4.00
    Bread       | 1        | $2.50
    """
    d.text((50, 50), text, fill=(0,0,0), font=font)
    img.save(filename)

def create_non_table_image(filename):
    img = Image.new('RGB', (800, 400), color = (255, 255, 255))
    d = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except IOError:
        font = ImageFont.load_default()

    text = "This is just a regular sentence.\nIt is not a table.\nThere are no rows or columns here."
    d.text((50, 50), text, fill=(0,0,0), font=font)
    img.save(filename)

if __name__ == "__main__":
    create_table_image("table_test.png")
    create_non_table_image("non_table_test.png")
    print("Test images created.")
