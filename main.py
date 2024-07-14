from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import google.oauth2.id_token;
from google.auth.transport import requests
from google.cloud import firestore
import starlette.status as status 
from fastapi import Form
from datetime import datetime


# Create a FastAPI instance
app = FastAPI()
# Initialize Firestore DB
firestore_db = firestore.Client()
# Initialize Firebase request adapter
firebase_request_adapter = requests.Request()
# Mount the static files directory
app.mount('/static', StaticFiles(directory='static'), name='static')
# Initialize Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Define a function to get the user from Firestore
def getUser(user_token):
# Get the user document from Firestore
    user = firestore_db.collection('users').document(user_token['user_id'])

# If the user does not exist, create a new user document
    if not user.get().exists:
        user_data = {
            'name': 'User'
            

        }
        # Set the user document in Firestore
        firestore_db.collection('users').document(user_token['user_id']).set(user_data)
# Return the user document
    return user
# Define a function to validate the Firebase token
def validateFirebaseToken(id_token):
    # Check if the ID token is None
    if not id_token:
        return None

    user_token = None
    # Try to verify the token and get the user information
    try:
        # Verify the token
        user_token = google.oauth2.id_token.verify_firebase_token(
            id_token, firebase_request_adapter)
    # Handle the error appropriately, maybe log it or return a message to the user
    except ValueError as err:
        print(str(err)) 
    # Return the user information
    return user_token

# Define the root route
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    # Get the ID token from the request cookies
    id_token = request.cookies.get("token")

    # Validate the Firebase token
    user_token = validateFirebaseToken(id_token)
    # Get the EV list from Firestore
    Ev_list= firestore_db.collection('ev').get()
    # If there is no valid user token, return the main page without user information
    if not user_token:
        # If there is no valid user token, return the main page without user information
        return templates.TemplateResponse('main.html', {'request': request, 'user_token': None, 'error_message': None, 'user_info': None,'Ev_list':Ev_list})
     # Get the user document from Firestore
    user = getUser(user_token)
       # Return the main page with the user information
    return templates.TemplateResponse('main.html', {'request': request, 'user_token': user_token, 'error_message': None, 'user_info': user.get(), 'Ev_list': Ev_list})

# Query route
@app.get("/query-result", response_class=HTMLResponse)
# Define the query_result route
async def query_result(request: Request, attribute: str, value: str = None, lower_limit: str = None, upper_limit: str = None):
    # Get the ID token from the request cookies
    try:
        query = firestore_db.collection('ev')
        
        # Check for value query or range query
        if value:
            query = query.where(attribute, "==", value)
        else:
            # Ensure lower and upper limits are provided for range queries
            if lower_limit and upper_limit:
                # Validate that lower and upper limits are integers
                try:
                    lower_int = int(lower_limit)
                    upper_int = int(upper_limit)
                    query = query.where(attribute, ">=", lower_int).where(attribute, "<=", upper_int)
                except ValueError:
                    # Handle invalid numerical inputs gracefully
                    return templates.TemplateResponse("query_results.html", {
                        "request": request, 
                        "filtered_results": [], 
                        "error": "Invalid numerical range provided."
                    })
        
        # Execute the query and collect results
        results = query.stream()
        # Convert the results to a list of dictionaries
        filtered_results = [doc.to_dict() for doc in results]
        
        if not filtered_results:
            # No results found case
            return templates.TemplateResponse("query_results.html", {
                "request": request, 
                "filtered_results": filtered_results, 
                "error": "No results found matching your criteria."
            })

        # Return the successful query results
        return templates.TemplateResponse("query_results.html", {
            "request": request, 
            "filtered_results": filtered_results
        })
        # Handle the error appropriately, maybe log it or return a message to the user
    except Exception as e:
        # Log the error for debugging
        print(f"Error during query: {e}")
        # Return an error message to the user
        return templates.TemplateResponse("query_results.html", {
            "request": request, 
            "filtered_results": [], 
            "error": "An error occurred while processing your request."
        })



# Define the login route
@app.get("/add-ev", response_class=HTMLResponse)
async def add_ev_page(request: Request):
    # Get the ID token from the request cookies
    id_token = request.cookies.get("token")
    # Validate the Firebase token
    user_token = validateFirebaseToken(id_token)
    # If there is no valid user token, redirect to the main page or show an error
    if not user_token:
      
        return RedirectResponse('/')

    # Get the user document from Firestore
    user = getUser(user_token)
     # Return the add EV page
    return templates.TemplateResponse('add-ev.html', {'request': request, 'user_token': None, 'error_message': None, 'user_info': None})
     # Define the login route
@app.post("/add-ev", response_class=RedirectResponse)
async def add_ev(request: Request):
    # Retrieve the ID token from the request cookies
    id_token = request.cookies.get("token")
    # Validate the Firebase token to ensure the user is logged in
    user_token = validateFirebaseToken(id_token)
    # Redirect to the main page or a login page if there's no valid user token
    if not user_token:
        return RedirectResponse('/login', status_code=status.HTTP_303_SEE_OTHER)
    # Retrieve the form data
    form = await request.form()

    # Check for an existing EV with the same name
    ev_query = firestore_db.collection('ev').where('Name', '==', form['Name']).get()

    # If an EV with the same name exists, prevent adding a new one and redirect or notify the user
    if len(list(ev_query)) > 0:
        # This is a simple redirect with an error query parameter. Consider implementing a more user-friendly feedback mechanism.
        return RedirectResponse('/add-ev?error=EV name already exists', status_code=status.HTTP_303_SEE_OTHER)

    # If no duplicate name is found, proceed with adding the new EV
    new_ev = firestore_db.collection('ev').document()
    new_ev.set({
        'Name': form['Name'],
        'Manufacturer': form['Manufacturer'],
        'Year':(form['Year']),
        'Battery_size': form['Battery_size'],
        'Range_WLTP': form['Range_WLTP'],
        'Cost': form['Cost'],
        'Power': form['Power'],
        'reviews': []
    })

    # Redirect to the main page after successful addition
    return RedirectResponse('/', status_code=status.HTTP_302_FOUND)

    # Define the login route
@app.get("/ev/{ev_id}", response_class=HTMLResponse)
# Define the EV details route
async def show_ev(request: Request, ev_id: str):
    # Fetch EV details
    ev_doc = firestore_db.collection('ev').document(ev_id).get()
    # If the EV document does not exist, raise an HTTP 404 error
    if not ev_doc.exists:
        raise HTTPException(status_code=404, detail="EV not found")
    ev_data = ev_doc.to_dict()
    ev_data['id'] = ev_id  # Included the document ID for edit/delete actions
    return templates.TemplateResponse("ev_info.html", {"request": request, "ev": ev_data})

# Define the edit EV route
@app.get("/edit-ev/{ev_id}", response_class=HTMLResponse)
# Define the edit_ev_page route
async def edit_ev_page(request: Request, ev_id: str):
    # Fetch the EV document from Firestore
    ev_doc = firestore_db.collection('ev').document(ev_id).get()
    # If the EV document does not exist, raise an HTTP 404 error
    if not ev_doc.exists:
        raise HTTPException(status_code=404, detail="EV not found")
    return templates.TemplateResponse("edit_ev.html", {"request": request, "ev": ev_doc.to_dict(), "ev_id": ev_id})

# edit-ev route
@app.post("/edit-ev/{ev_id}", response_class=RedirectResponse)
# Define the submit_edit_ev route
async def submit_edit_ev(request: Request, ev_id: str):
    # Retrieve the form data
    form_data = await request.form()
    # Update the EV document in Firestore
    ev_data = dict(form_data)
    firestore_db.collection('ev').document(ev_id).set(ev_data)
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)

# Define the delete EV route
@app.post("/delete-ev/{ev_id}", response_class=RedirectResponse)
async def delete_ev(ev_id: str):
    # Delete the EV document from Firestore
    firestore_db.collection('ev').document(ev_id).delete()
    # Redirect to the main page after successful deletion
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

# Define the login route
@app.post("/compare-evs", response_class=HTMLResponse)
async def compare_evs(request: Request):
    # Retrieve the form data
    form_data = await request.form()
    ev1_id = form_data.get("ev1_id")
    ev2_id = form_data.get("ev2_id")
    ev1_doc = firestore_db.collection('ev').document(ev1_id).get()
    ev2_doc = firestore_db.collection('ev').document(ev2_id).get()
    ev1_data = ev1_doc.to_dict()
    ev2_data = ev2_doc.to_dict()

    # Initialize the comparison results dictionary
    comparison_results = {
        "Battery_size": "equal",
        "Cost": "equal",
        "Power": "equal",
    }

    # Compare each attribute and update comparison_results accordingly
    for attribute in comparison_results.keys():
        if ev1_data[attribute] > ev2_data[attribute]:
            comparison_results[attribute] = "ev1"
        elif ev1_data[attribute] < ev2_data[attribute]:
            comparison_results[attribute] = "ev2"
# Render the template with the comparison results
    return templates.TemplateResponse("compare_evs.html", {
        "request": request, 
        "ev1": ev1_data, 
        "ev2": ev2_data, 
        "comparison_results": comparison_results
    })

# Define the login route
def get_ev_reviews(ev_id):
    # Fetch the EV document from Firestore
    ev_doc = firestore_db.collection('ev').document(ev_id).get()
    reviews = []
    
# Fetch all reviews for the specified EV
    for review in ev_doc.get('review_list'):
        reviews.append(review.get())
        # Return the reviews
    return "reviews"

# Define the login route
@app.post("/add-review/{ev_id}", response_class=RedirectResponse)
async def add_review(request: Request, ev_id: str):
    # Retrieve the ID token from the request cookies
    id_token = request.cookies.get("token")
    # Validate the Firebase token to ensure the user is logged in
    user_token = validateFirebaseToken(id_token)
    if not user_token:
        # Redirect to a login page or the main page if there's no valid user token
        return RedirectResponse('/', status_code=status.HTTP_303_SEE_OTHER)
    # Retrieve the form data
    form = await request.form()
    
    # Create a new review document in Firestore under the 'reviews' collection
    review_ref = firestore_db.collection('reviews').document()
    review_ref.set({
        'content': form['content'],# content is the name of the input field in the form
        'rating': form['rating'], # rating is the name of the input field in the form
        'user_id': user_token['user_id'],  # Associate this review with the logged-in user
        'created_at': datetime.utcnow()  # Capture the time the review was submitted
    })
    
    # Update the 'reviews' field in the EV document with the new review reference
    ev_doc = firestore_db.collection('ev').document(ev_id)
    # Fetch the existing reviews and append the new review reference
    reviews = ev_doc.get().get('reviews')
    # Append the new review reference to the existing reviews
    reviews.append(review_ref)
    # Update the 'reviews' field in the EV document
    ev_doc.update( { 'reviews': reviews } )
    
    # Redirect to the EV details page after successfully adding the review
    return RedirectResponse('/', status_code=status.HTTP_302_FOUND)

# Define the login route
@app.get("/ev/{ev_id}", response_class=HTMLResponse)
# Define the EV details route
async def show_ev(request: Request, ev_id: str):
    # Fetch EV details
    ev_doc = firestore_db.collection('ev').document(ev_id).get()
    # If the EV document does not exist, raise an HTTP 404 error
    if not ev_doc.exists:
        raise HTTPException(status_code=404, detail="EV not found")
        # Convert the EV document to a dictionary
    ev_data = ev_doc.to_dict()
    ev_data['id'] = ev_id

    # Fetch reviews and user_token
    reviews = get_ev_reviews(ev_id)
    user_token = validateFirebaseToken(request.cookies.get("token"))

    # calculate the average score
    average_score = calculate_average_score(ev_id)

    # Render template with all necessary data
    return templates.TemplateResponse("ev_info.html", {
        "request": request, 
        "ev": ev_data, 
        "reviews": reviews, 
        "user_token": user_token,
        "average_score": average_score
    })



# Define the login route
def calculate_average_score(ev_id):
    # Fetch all reviews for the specified EV
    reviews_ref = db.collection('reviews').where('ev_id', '==', ev_id)
    reviews = reviews_ref.stream()
# Calculate the total score and review count
    total_score = 0
    review_count = 0
    # Iterate over each review and calculate the total score
    for review in reviews:
        # Convert the review document to a dictionary
        review_data = review.to_dict()
        total_score += review_data.get('score', 0)  # Assuming each review has a 'score' field
        review_count += 1 # Increment the review count

    # Calculate the average score
    if review_count > 0:
        # Calculate the average score
        average_score = total_score / review_count
        return round(average_score, 2)  # Rounding to 2 decimal places for readability
    else:
        return None  # Or return 0, or another indicator of 'No Reviews'

# Define the login route
@app.post("/compare-evs", response_class=HTMLResponse)
# Define the compare_evs route
async def compare_evs(request: Request):
    # Retrieve the form data
    ev1_average_score = calculate_average_score(ev1_id)
    ev2_average_score = calculate_average_score(ev2_id)
    # Compare the average scores of the two EVs
    comparison_results['Average_Score'] = "ev1" if ev1_average_score > ev2_average_score else "ev2" if ev1_average_score < ev2_average_score else "equal"
    # Render the template with the comparison results
    return templates.TemplateResponse("compare_evs.html", {
        "request": request,
        "ev1": ev1_data,
        "ev2": ev2_data,
        "comparison_results": comparison_results,
        "ev1_average_score": ev1_average_score,
        "ev2_average_score": ev2_average_score
    })


    
    



    



