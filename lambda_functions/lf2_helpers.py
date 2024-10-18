def reorder_dict(d, key_order):
    """Reorder keys in a dictionary."""
    return {key: d[key] for key in key_order if key in d}


def create_email_body(data, user_dining_preferences):
    html_table = f"""<html>
            <head></head>
            <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
            <div style="background-color: #ffffff; border-radius: 10px; padding: 20px; max-width: 600px; margin: auto;">
            <h2 style="color: #333333; text-align: center;">Hello! Here are my {user_dining_preferences['cuisine'].title()} Restaurant suggestions for {user_dining_preferences['people']} people, at {user_dining_preferences['time']} on {user_dining_preferences['date']}, in {user_dining_preferences['city'].title()}</h2>
            <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">"""

    # Add table header
    html_table += "<thead>"
    html_table += "<tr style='background-color: #f8c471; color: #ffffff; text-align: left;'>"
    for key in data[0].keys():
        html_table += f"<th style='padding: 10px; border-bottom: 1px solid #dddddd;'>{key.title()}</th>"
    html_table += "</tr>"
    html_table += "</thead>"

    # Add table rows
    html_table += "<tbody>"
    for item in data:
        html_table += "<tr>"
        for key, value in item.items():
            html_table += f"<td style='padding: 10px; border-bottom: 1px solid #dddddd;'>{str(value).title()}</td>"
        html_table += "</tr>"
    html_table += "</tbody>"

    # Close HTML table
    html_table += """</table>
        <p style="font-size: 16px; color: #333333; text-align: center; margin-top: 30px;">Hope you like our suggestions!<br><br></p><h4>Best,<br>Arsalan Anwar & Pratham Shah</h4>
        </div>
        </body>
    </html>"""

    return html_table