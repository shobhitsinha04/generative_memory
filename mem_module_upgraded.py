import json
from typing import List, Tuple
import openai
from datetime import datetime, timedelta
import spacy 

# OpenAI API 
openai.api_key = 'api-key'

class MemoryModule:
    def __init__(self):
        # dictionary to store daily activities 
        self.daily_activities = {}  # dict[str(persona id), dict[str, List[List[str]]](dict with key as date and value is the list of activities) ]

        # dictionary to store daily summaries 
        self.summaries = {} 
        # dict[str(persona id), dict[str, str](dict with str as date and string as the summary)] 

        # dictionary to store weekly summaries
        self.weekly_summaries = {} 
        #  dict[str(persona id), dict[int, str](dict with key number as int and string as the weekly summary)]

        # counter to keep track of the number of days
        self.day_counters = {} 
        # dict[str, int] (dict with key as persona id and value as the number of accesses)

        # dictionary to store monthly summaries 
        self.monthly_summaries = {} 
        # dict[str(persona id), dict[str, str](dict with the key as the month and the value as the monthly summary)]

        # counter to see how many times a memory is accessed 
        self.memory_access_counter = {} 
        # dict[str(persona id), dict[str, int](dict with the key as the date and the value is the number of the times the memory is accessed)]

        #  pre defined threshold 
        self.memory_threshold = 0.5 
        #YET TO DECIDE THE VALUE

        # Loading the spaCy model
        self.nlp = spacy.load("en_core_web_sm") #check

    def store_daily_activities(self, activities_dict: dict[str, dict[str, List[List[str]]]]):
        """
        Stores the activities for a specific date and persona.
        activities_dict: A dictionary containing the activities for each persona and date.
        Sample format: {"1": {"2024-07-10": [["sleep", "(00:00, 08:11)"], ...]}}
        """
        for persona_id, dates in activities_dict.items():
            if persona_id not in self.daily_activities:
                self.daily_activities[persona_id] = {}
                self.day_counters[persona_id] = 0
            for date, activities in dates.items():
                self.daily_activities[persona_id][date] = activities
                self.day_counters[persona_id] += 1


    ########################################################################################## 
    # FOR SUMMARIZATION
    ########################################################################################## 
    def summarize_day(self, persona_id: str, date: str):
        """
        Summarizes the activities of a specific day for a specific persona using GPT model.
        persona_id: The ID of the persona
        date: The date of the activities to be summarized.
        """
        #retrieve the activities for each date and then converts the activties to a json string format for input to the LLM
        activities = self.daily_activities.get(persona_id, {}).get(date, [])
        activities_json = json.dumps(activities)
        
        # Call OpenAI's API to generate a summary of the activities
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": f"Please summarize the following activities for the day in a concise, coherent paragraph: {activities_json}"}
                ],
                max_tokens=100,
            )
        except openai.OpenAIError as e:
            print(f"Error generating summary: {e}")
            return
            
        # Get the summary text from the response and store it in the summaries dictionary  
        summary = response['choices'][0]['message']['content'].strip()

        if persona_id not in self.summaries:
            self.summaries[persona_id] = {}
        self.summaries[persona_id][date] = summary

        # initalize the memory access counter for the date
        if persona_id not in self.memory_access_counter:
            self.memory_access_counter[persona_id] = {}
        self.memory_access_counter[persona_id][date] = 0
        # return summary


    def summarize_week(self, persona_id: str, end_date: str):
        """
        Summarizes the activities of a specific week for a specific persona using GPT model.
        persona_id: The ID of the persona.
        end_date: The end date of the week to be summarized.
        """
        # making the date in the right format 
        end_date_dt = datetime.strptime(end_date, '%d-%m-%Y')

        # get the last 7 dates before
        dates = []
        for i in range(7):
            date = end_date_dt - timedelta(days=i)
            dates.append(date.strftime('%d-%m-%Y'))

        # then combine daily summaries of those 7 days
        input_weekly_summary = []
        for date in dates:
            # Checking if the date exists in the summaries dictionary
            if date in self.summaries.get(persona_id, {}):
                input_weekly_summary.append(self.summaries[persona_id][date])

        input_weekly_summary = " ".join(input_weekly_summary)

        # call the api to generate the summary
        try: 
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": f"Here are the daily summaries for the week ending on {end_date}. Please provide a concise and coherent weekly summary in a single paragraph, focusing on the main activities and events:\n{input_weekly_summary}"}
                ],
                max_tokens=200,
            )
        except openai.OpenAIError as e:
            print(f"Error generating weekly summary: {e}")
            return

        weekly_summary = response['choices'][0]['message']['content'].strip()
        week_number = end_date_dt.isocalendar()[1]
        
        if persona_id not in self.weekly_summaries:
            self.weekly_summaries[persona_id] = {}

        self.weekly_summaries[persona_id][week_number] = weekly_summary

    
    def summarize_month(self, persona_id: str, end_date: str):
        """
        Summarizes the activities of a specific month using GPT model.
        persona_id: The ID of the persona.
        end_date: The end date of the month to be summarized.
        """
        end_date_dt = datetime.strptime(end_date, '%d-%m-%Y')
        start_date_dt = end_date_dt.replace(day=1)

        daywise_summaries = {
            "Monday": [],
            "Tuesday": [],
            "Wednesday": [],
            "Thursday": [],
            "Friday": [],
            "Saturday": [],
            "Sunday": []
        }

        current_date_dt = start_date_dt
        # loop through all the days of the month
        while current_date_dt <= end_date_dt: 
            date_str = current_date_dt.strftime('%d-%m-%Y')
            day_name = current_date_dt.strftime('%A')

            # if a summary exists for that day then add it to the dict 
            if date_str in self.summaries.get(persona_id, {}):
                daywise_summaries[day_name].append(self.summaries[persona_id][date_str])
            
            current_date_dt += timedelta(days=1)

        monthly_summary = {}

        for day, summaries in daywise_summaries.items():
            if summaries:
                input_monthly_summary = " ".join(summaries)

                try:
                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant."},
                            {"role": "user", "content": f"Please summarize the following activities for all {day}s in the month in a structured and coherent paragraph:\n{input_monthly_summary}"}
                        ],
                        max_tokens=300,
                    )
                except openai.OpenAIError as e:
                    print(f"Error generating monthly summary for {day}: {e}")
                    continue

                monthly_summary[day] = response['choices'][0]['message']['content'].strip()

                # formatted_response = response['choices'][0]['message']['content'].strip()
                # # Ensuring the first letter of the response is capitalized
                # monthly_summary[day] = formatted_response[0].upper() + formatted_response[1:]

        month_year = end_date_dt.strftime('%m-%Y')
        if persona_id not in self.monthly_summaries:
            self.monthly_summaries[persona_id] = {}

        self.monthly_summaries[persona_id][month_year] = monthly_summary
                           
    ########################################################################################## 
    # FOR RETRIEVAL
    ########################################################################################## 

    def retrieve_tasks_by_intention(self, persona_id: str, intention: str):
        """
        Retrieves historical tasks based on a specific intention by searching through summaries.
        persona_id: The ID of the persona.
        intention: The intention to search for in the summaries.
        returns a list of tuples containing the date and summary where the intention was found. Format will be List[Tuple[str, str]].
        """
        relevant_tasks = []
        for date, summary in self.summaries.get(persona_id, {}).items():
            if intention in summary:
                # Increase the access frequency of that date
                self.memory_access_counter[persona_id][date] += 1
                relevant_tasks.append((date, summary))
        return relevant_tasks
    
    ##########################################################################################
    # FOR MEMORY DELETION
    ##########################################################################################
    def calculate_information_density(self, summary: str):
        """
        Calculates the weighted information density of a summary.
        Output would be a float
        """
        categories = {
            "events" : 0.5, # (e.g., "passed a test," "attended a meeting")   #check if you can personalize this
            "entities": 0.2, # (e.g., "person," "location")
            "actions": 0.3, # (e.g., "completed," "started")
            "attributes": 0.3 # (e.g., "high score," "difficult task")
        }
        # NER using spacy
        doc = self.nlp(summary)

        # Initial counts of each type of thing
        counts = {
            "events": 0,
            "entities": 0,
            "actions": 0,
            "attributes": 0
        }

        # Going through summaries to see how much of each type is present in the summary
        for ent in doc.ents:
            if ent.label_ in ["EVENT"]:
                counts["events"] += 1
            elif ent.label_ in ["PERSON", "ORG", "GPE", "LOC"]:
                counts["entities"] += 1

        for token in doc:
            if token.pos_ in ["VERB"]:
                counts["actions"] += 1
            elif token.pos_ in ["ADJ", "ADV"]:
                counts["attributes"] += 1

        weighted_sum = sum(categories[cat] * counts[cat] for cat in categories)
        total_words = len(summary.split())
        weighted_info_density = weighted_sum / total_words if total_words > 0 else 0

        return weighted_info_density
    
    def calculate_importance_score(self, persona_id: str, date: str, summary: str):
        """
        Calculates the importance score based on recency, frequency, and information density.
        """
        frequency = self.memory_access_counter.get(persona_id, {}).get(date, 0)
        recency = (datetime.now() - datetime.strptime(date, '%d-%m-%Y')).days
        weighted_info_density = self.calculate_information_density(summary)

        # Normalizing the recency and frequency 
        max_recency = 90 #last 3 months
        normalized_recency = 1 - min(recency / max_recency, 1) # it is (1 -) because the more recent memory should have higher score
        
        max_frequency = max(self.memory_access_counter.get(persona_id, {}).values(), default=0)  
        max_frequency = max(1, max_frequency)  # Ensure max_frequency is at least 1 to avoid division by zero
    
        
        normalized_frequency = min(frequency / max_frequency, 1)

        # Calculating the overall importance score for the memory
        importance_score = (normalized_frequency + normalized_recency + weighted_info_density) / 3

        return importance_score

    def deleting_memory(self):
        """
        Deletes the memory of the user based on the memory access threshold.
        """
        for persona_id, summaries in list(self.summaries.items()):
            for date, summary in list(summaries.items()):
                # iterates over the summaries dictionary and deletes the low scoring daily summaries and daily activities
                importance_score = self.calculate_importance_score(persona_id, date, summary)
                if importance_score < self.memory_threshold:
                    del self.summaries[persona_id][date]
                    self.memory_access_counter[persona_id].pop(date, None)
                    if date in self.daily_activities.get(persona_id, {}):
                        self.daily_activities[persona_id].pop(date, None)



# Testing the MemoryModule
if __name__ == "__main__":
    memory_module = MemoryModule()
    
    # Example activities for 7 days starting from today
    activities_dict = {
        "1": {
            "01-07-2024": [["go to sleep", "(00:00, 06:58)", "home"], ["eat breakfast", "(07:24, 08:00)", "home"], ["go to work", "(09:00, 12:00)", "unsw campus"], ["lunch", "(12:30, 13:00)"], ["meeting", "(13:30, 15:00)"]],
            "02-07-2024": [["go to sleep", "(00:00, 07:00)"], ["jogging", "(08:30, 09:30)"]],
            "03-07-2024": [["go to sleep", "(00:00, 06:45)"], ["eat breakfast", "(07:15, 07:45)"], ["office work", "(08:30, 12:00)"], ["lunch", "(12:30, 13:00)"]],
            "04-07-2024": [["go to sleep", "(00:00, 06:30)"], ["emails", "(08:00, 09:00)"], ["client call", "(11:30, 12:30)"], ["lunch", "(13:00, 13:30)"], ["project discussion", "(14:00, 16:00)"]],
            "05-07-2024": [["go to sleep", "(00:00, 07:15)"], ["marketing research", "(09:00, 11:00)"], ["brainstorming session", "(14:00, 16:00)"], ["report writing", "(16:30, 18:00)"]],
            "06-07-2024": [["go to sleep", "(00:00, 07:00)"], ["gardening", "(14:00, 16:00)"], ["dinner", "(18:00, 19:00)"]],
            "07-07-2024": [["go to sleep", "(00:00, 06:45)"], ["eat breakfast", "(07:15, 07:45)"], ["relaxing", "(08:00, 09:00)"], ["watch movie", "(10:00, 12:00)"], ["dinner", "(18:00, 19:00)"]]
        },
        "2": {
            "01-07-2024": [["sleep", "(23:00, 06:00)"], ["exercise", "(06:30, 07:30)"]],
            "02-07-2024": [["sleep", "(23:00, 06:00)"], ["breakfast", "(08:00, 08:30)"]],
            "03-07-2024": [["sleep", "(23:00, 06:00)"], ["online meeting", "(14:00, 15:00)"]],
        },
        "3": {
            "01-07-2024": [["sleep", "(22:00, 06:00)"], ["morning run", "(06:30, 07:00)"]],
            "02-07-2024": [["sleep", "(22:00, 06:00)"], ["breakfast", "(07:30, 08:00)"]],
            "03-07-2024": [["sleep", "(22:00, 06:00)"], ["work", "(09:00, 17:00)"]],
        },
        "4": {
            "01-07-2024": [["sleep", "(23:00, 07:00)"], ["yoga", "(07:30, 08:00)"]],
            "02-07-2024": [["sleep", "(23:00, 07:00)"], ["breakfast", "(08:30, 09:00)"]],
            "03-07-2024": [["sleep", "(23:00, 07:00)"], ["work", "(10:00, 16:00)"]],
        }
    }

    # Storing activities and generating summaries for each day
    memory_module.store_daily_activities(activities_dict)
    for persona_id, dates in activities_dict.items():
        for date in dates.keys():
            memory_module.summarize_day(persona_id, date)
            print(f"Summary for persona {persona_id} on {date}: {memory_module.summaries[persona_id][date]}")
            print("\n")
            
            # Check if 7 days have passed to generate a weekly summary
            if memory_module.day_counters[persona_id] % 7 == 0:
                memory_module.summarize_week(persona_id, date)

    # Check the generated weekly summary
    week_number = datetime.strptime("07-07-2024", '%d-%m-%Y').isocalendar()[1]
    for persona_id in activities_dict.keys():
        # Debugging statement
        print(f"Week number: {week_number}")
        if week_number in memory_module.weekly_summaries.get(persona_id, {}):
            print(f"Weekly summary for persona {persona_id} for week {week_number}: {memory_module.weekly_summaries[persona_id][week_number]}")
        else:
            print(f"No weekly summary found for persona {persona_id} for week {week_number}")
        print("\n")
    
    # Example: Generating and checking the monthly summary
    end_date_str = "07-07-2024"  # Assume 7 days have passed
    for persona_id in activities_dict.keys():
        memory_module.summarize_month(persona_id, end_date_str)
        month_year = datetime.strptime(end_date_str, '%d-%m-%Y').strftime('%m-%Y')
        print(f"Monthly summary for persona {persona_id} for {month_year}: {memory_module.monthly_summaries[persona_id][month_year]}")
        print("\n")
    
    # Example: Retrieving historical tasks based on intention
    intention = "eat breakfast"
    for persona_id in activities_dict.keys():
        tasks = memory_module.retrieve_tasks_by_intention(persona_id, intention)
        print(f"Historical tasks for persona {persona_id} with intention '{intention}': {tasks}")
    
    # Example: Deleting less important information
    memory_module.deleting_memory()
    for persona_id in activities_dict.keys():
        print(f"Summaries for persona {persona_id} after deletion: {memory_module.summaries[persona_id]}")


