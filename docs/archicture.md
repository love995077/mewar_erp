
## to ativate 
"D:/Shifting Folder/chatbotai/env/Scripts/Activate.ps1"

.\env\Scripts\activate 

## to run 
uvicorn app.main:app --reload

 uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

## streamlit
streamlit run app/streamlit_app.py

## analytics_dasboard
streamlit run analytics_dashboard.py

## for testing bot
pytest test_bot.py -v

# modal deploy 
modal deploy modal_deploy.py  

## whtsapp
modal deploy modal_deploy.py

## agent
python -m streamlit run app/ai_agents/ai_dashboard.py


## n8n
docker run -d --name my-n8n -p 5678:5678 -v n8n_data:/home/node/.n8n n8nio/n8n

## direct n8n without docker 
npx n8n

## run n8n
npx n8n

## delete po

http://127.0.0.1:8000/api/delete-test-po