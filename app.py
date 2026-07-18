from flask_cors import CORS

CORS(
    app,
    origins=[
        "https://rdvaliahnach.netlify.app"
    ]
)