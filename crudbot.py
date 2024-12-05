import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import re
import os
import threading
from utils.anomaly_checker import run_periodically

# Function to load a CSV file into a DataFrame
def load_csv(file_path):
    try:
        df = pd.read_csv(file_path)
        return df
    except Exception as e:
        st.error(f"Error loading CSV file: {e}")
        return None

# Function to save the DataFrame to a CSV file
def save_csv(df, file_path, trigger):
    try:
        df.to_csv(file_path, index=False)
        if trigger == "update":
            st.success("File updated successfully.")
        elif trigger == "add":
            st.success("Record(s) added successfully.")
        elif trigger == "delete":
            st.success("Records deleted successfully.")
        else:
            st.success("Changes made to File were successful")
    except Exception as e:
        st.error(f"Error saving CSV file: {e}")

# Function to add a record
def add_record(new_data, df, file_path):
    try:
        # Ensure the input is a dictionary
        if not isinstance(new_data, dict):
            return "Error: The new record data must be a dictionary."

        # Validate that all specified columns exist in the DataFrame
        missing_columns = [col for col in new_data.keys() if col not in df.columns]
        if missing_columns:
            return f"Error: The following columns are missing in the dataset: {', '.join(missing_columns)}"

        # Create a new row as a DataFrame
        new_row = pd.DataFrame([new_data], columns=df.columns)

        # Concatenate the new row with the original DataFrame
        df = pd.concat([df, new_row], ignore_index=True)

        # Save back to the file
        df.to_csv(file_path, index=False)
        # return "Record added successfully."
        return new_row
    except Exception as e:
        return f"Error adding record: {e}"



# Function to update records based on a condition
def update_record(condition, update_values, df, file_path):
    try:
        for col, value in update_values.items():
            df.loc[condition, col] = value
        save_csv(df, file_path, "update")
        # return "Records updated successfully."
        return df
    except Exception as e:
        st.error(f"Error updating records: {e}")
        return "Error updating records."

# Function to delete records based on a condition
def delete_record(condition, df, file_path):
    try:
        df = df[~condition]  # Filter out rows that match the condition
        # deleted_df = df[condition]
        save_csv(df, file_path, "delete")
        return "Deleted Successfully"
    except Exception as e:
        st.error(f"Error deleting records: {e}")
        return "Error deleting records."


# Function to handle various user queries
def handle_instruction(instruction, df, file_path):
    try:
        # Debug: Log initial DataFrame state and instruction
        # st.write("Initial DataFrame preview:")
        # st.write(df.head())

        # st.write("Instruction received:", instruction)

        # Handle "add" queries
        if "add" in instruction.lower():
            # Assuming a simple format: "Add a record where column1 is value1, column2 is value2, ..."
            pattern = re.findall(r"(\w+)\s*is\s*([\w\s]+)", instruction, re.IGNORECASE)
            if not pattern:
                return "Could not parse the addition instruction. Please follow the format: 'Add a record where column1 is value1, column2 is value2, ...'"

            new_data = {}
            for col, value in pattern:
                if col in df.columns:
                    new_data[col] = value

            if not new_data:
                return "No valid columns found for the new record."

            result = add_record(new_data, df, file_path)
            st.success("Record Added successfully.")
            return result

        # Handle "update" queries
        if ("update" in instruction.lower()) or ("edit" in instruction.lower()) or ("set" in instruction.lower()):
        # if "update" in instruction.lower():
            # Match "Update column to value where condition"
            condition_match = re.search(
                r"update\s+(\w+)\s+to\s+([\w\s\d.]+)\s+where\s+(.+)",
                instruction,
                re.IGNORECASE,
            )
            if not condition_match:
                return "Could not parse the update instruction. Please follow the format: 'Update column to value where condition'."
            print(condition_match.groups())
            column_to_update = condition_match.group(1).strip()
            new_value = condition_match.group(2).strip()
            condition = condition_match.group(3).strip()
            print(condition)
            print(condition_match.groups())
            # Ensure column exists
            if column_to_update not in df.columns:
                return f"Column '{column_to_update}' not found in the DataFrame."

            # Split conditions by "or"
            or_conditions = [cond.strip() for cond in condition.split(" or ")]

            # Initialize the complete query
            complete_query = None

            for or_condition in or_conditions:
                # Parse each individual condition (supports AND within OR groups)
                and_conditions = [cond.strip() for cond in or_condition.split(" and ")]
                sub_query = None

                for and_condition in and_conditions:
                    match = re.search(
                        r"(\w+)\s+(is|equals|contains|greater than|less than)\s+([\w\s\d.]+)",
                        and_condition,
                        re.IGNORECASE,
                    )
                    if not match:
                        return f"Could not parse the condition: {and_condition}"

                    col, operator, value = match.groups()
                    col, value = col.strip(), value.strip()

                    if col not in df.columns:
                        return f"Column '{col}' not found in the DataFrame."

                    # Handle numeric or string conditions
                    if pd.api.types.is_numeric_dtype(df[col]):
                        if operator in ["greater than", "less than"]:
                            value = float(value) if value.replace(".", "", 1).isdigit() else value
                            condition_clause = df[col] > value if operator == "greater than" else df[col] < value
                        else:
                            value = float(value) if value.replace(".", "", 1).isdigit() else value
                            condition_clause = df[col] == value
                    else:
                        df[col] = df[col].astype(str)  # Ensure string comparison
                        if operator in ["is", "equals"]:
                            condition_clause = df[col].str.lower() == value.lower()
                        elif operator == "contains":
                            condition_clause = df[col].str.contains(value, case=False, na=False)
                        else:
                            return f"Unsupported operator: {operator}"

                    sub_query = condition_clause if sub_query is None else sub_query & condition_clause

                # Combine OR conditions
                complete_query = sub_query if complete_query is None else complete_query | sub_query

            if complete_query is None:
                return "Could not construct the condition. Please check your syntax."

            # Ensure new_value is compatible with the target column
            if pd.api.types.is_numeric_dtype(df[column_to_update]):
                new_value = float(new_value) if new_value.replace(".", "", 1).isdigit() else new_value
            else:
                new_value = str(new_value)

            # Perform the update
            df.loc[complete_query, column_to_update] = new_value

            # Save the updated DataFrame to the file
            df.to_csv(file_path, index=False)
            # return f"Records updated successfully in column '{column_to_update}'."
            st.success("File updated successfully.")
            return df

        # Handle "delete" queries
        if (("delete" in instruction.lower())) or ("remove" in instruction.lower()):
            # Match "Delete records where column operator value"
            condition_match = re.search(
                r"(\w+)\s+(greater than|less than|equals|is|contains)\s+([\w\s\d.]+)",
                # r"delete data where\s+(\w+)\s+(greater than|less than|equals|is|contains)\s+([\w\s\d.]+)",
                # r"(delete|remove)\s+[\w\s]+\s+where\s+(greater than|less than|equals|is|contains|has)\s+([\w\s\d.]+)",
                instruction,
                re.IGNORECASE,
            )
            print(condition_match.groups())
            if not condition_match:
                return "Could not parse the delete instruction. Please follow format `delete(or 'remove') records where [your condition values]` or specify the condition using 'greater than', 'less than', 'equals', or 'contains'."
            
            col = condition_match.group(1).strip()
            operator = condition_match.group(2).lower()
            value = condition_match.group(3).strip()
            # print(condition_match.groups())
            # Ensure column exists
            if col not in df.columns:
                return f"Column '{col}' not found in the DataFrame."

            # Identify column data type and condition
            if operator in ["greater than", "less than", "equals", "equal to"]:
                # Check if column can be coerced to numeric
                if pd.api.types.is_numeric_dtype(df[col]) or df[col].apply(lambda x: str(x).replace('.', '', 1).isdigit()).all():
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                    value = float(value) if value.replace(".", "", 1).isdigit() else value

                    # Create numeric condition
                    if operator == "greater than":
                        condition = df[col] > value
                    elif operator == "less than":
                        condition = df[col] < value
                    else:  # "equals" or "equal to"
                        condition = df[col] == value
                else:
                    return f"Column '{col}' does not support numerical operations."
            elif operator in ["contains", "has"]:
                # Ensure the column is string-compatible
                if not pd.api.types.is_string_dtype(df[col]):
                    df[col] = df[col].astype(str)
                condition = df[col].str.contains(value, case=False, na=False)
            elif operator in ["is"]:
                if not pd.api.types.is_string_dtype(df[col]):
                    df[col] = df[col].astype(str)
                condition = df[col].fillna('').str.lower() == value.lower()
            else:
                return "Unsupported operator. Use 'greater than', 'less than', 'equals', or 'contains'."

            # Perform deletion
            result = delete_record(condition, df, file_path)

            return result


        # Handle "how many" queries and other operations...
        # (Add the existing code from your previous `handle_instruction` function here.)

        # Handle "how many" or "find all" queries involving dates
        if ("how many" in instruction.lower() or "find" in instruction.lower()) and "date" in instruction.lower():
            # Identify date-related columns
            date_columns = [col for col in df.columns if "date" in col.lower()]
            if not date_columns:
                return "No date columns found in the dataset."

            date_column = date_columns[0]
            df[date_column] = pd.to_datetime(df[date_column], errors='coerce')

            # Check for keywords like "today" or "yesterday"
            if "today" in instruction.lower():
                today = datetime.now().date()
                matching_records = df[df[date_column].dt.date == today]
                count = matching_records.shape[0]

                # Display table or return count based on query type
                if "find" in instruction.lower():
                    return matching_records
                    # st.table(matching_records)
                    # return f"Displayed all records dated today. Total records: {count}."
                return f"Number of records dated today: {count}"

            if "yesterday" in instruction.lower():
                yesterday = (datetime.now() - timedelta(days=1)).date()
                matching_records = df[df[date_column].dt.date == yesterday]
                count = matching_records.shape[0]

                # Display table or return count based on query type
                if "find" in instruction.lower():
                    return matching_records
                    # st.table(matching_records)
                    # return f"Displayed all records dated yesterday. Total records: {count}."
                return f"Number of records dated yesterday: {count}"

            # Check for specific date queries like "How many records are on 2024-08-10?"
            specific_date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", instruction)
            if specific_date_match:
                specific_date = pd.to_datetime(specific_date_match.group(1)).date()
                matching_records = df[df[date_column].dt.date == specific_date]
                count = matching_records.shape[0]

                # Display table or return count based on query type
                if "find" in instruction.lower():
                    # st.table(matching_records)
                    return matching_records
                    # return f"Displayed all records dated {specific_date}. Total records: {count}."
                return f"Number of records with a date of {specific_date}: {count}"

            # Handle date-based conditions like "after", "before", or "on"
            condition_match = re.search(r"(after|before|on)[\s]*(\d{4}-\d{2}-\d{2})", instruction, re.IGNORECASE)
            if condition_match:
                condition_type = condition_match.group(1).lower()
                condition_value = pd.to_datetime(condition_match.group(2)).date()

                if condition_type == "after":
                    matching_records = df[df[date_column].dt.date > condition_value]
                elif condition_type == "before":
                    matching_records = df[df[date_column].dt.date < condition_value]
                elif condition_type == "on":
                    matching_records = df[df[date_column].dt.date == condition_value]
                else:
                    return "Condition type not supported for dates. Use 'after', 'before', or 'on'."

                count = matching_records.shape[0]

                # Display table or return count based on query type
                if "find" in instruction.lower():
                    return matching_records
                    # st.table(matching_records)
                    # return f"Displayed all records where {date_column} is {condition_type} {condition_value}. Total records: {count}."
                return f"Number of records where {date_column} is {condition_type} {condition_value}: {count}"

            # Return if no matching date query was found
            return "Could not understand the date condition. Please use keywords like 'after', 'before', 'on', or a specific date."


        # Handle general "how many" queries (runs only if no date-specific query matched)
        elif "how many" in instruction.lower():
            # Identify the column and value
            column_names = df.columns.tolist()
            found_columns = [col for col in column_names if col.lower() in instruction.lower()]

            if not found_columns:
                return "No matching column found. Please try a different instruction."

            # Assume the first found column is the one user intended
            column = found_columns[0]
            condition_match = re.search(r"(greater than|less than|equals|is|of|before|after)[\s]*([\w\s]+)", instruction, re.IGNORECASE)

            if not condition_match:
                return "Could not understand the condition. Please use keywords like 'greater than', 'less than', 'equals', etc."

            condition_type = condition_match.group(1).lower()
            condition_value = condition_match.group(2).strip()

            # Convert condition_value to the appropriate type
            if condition_value.replace('.', '', 1).isdigit():
                condition_value = float(condition_value)
            elif condition_value.lower() in ["true", "false"]:
                condition_value = condition_value.lower() == "true"

            # Convert numeric-like columns to numeric type
            if pd.api.types.is_numeric_dtype(df[column]) or df[column].apply(lambda x: str(x).replace('.', '', 1).isdigit()).all():
                df[column] = pd.to_numeric(df[column], errors='coerce')

            # Count records based on the condition
            if condition_type in ["greater than", "after"]:
                count = df[df[column] > condition_value].shape[0]
            elif condition_type in ["less than", "before"]:
                count = df[df[column] < condition_value].shape[0]
            elif condition_type in ["equals", "is", "of"]:
                if pd.api.types.is_numeric_dtype(df[column]):
                    count = df[df[column] == condition_value].shape[0]
                else:
                    count = df[df[column].str.contains(condition_value, case=False, na=False)].shape[0]
            else:
                return "Condition type not supported for counting. Please use 'greater than', 'less than', or 'equals'."

            # Debug: Log count
            # st.write(f"Count for condition '{condition_type} {condition_value}':", count)
            return f"Number of records where {column} {condition_type} '{condition_value}': {count}"


        # Handle queries to display filtered results
        column_names = df.columns.tolist()
        found_columns = [col for col in column_names if col.lower() in instruction.lower()]

        if not found_columns:
            return "No matching column found. Please try a different instruction."

        # Assume the first found column is the one user intended
        column = found_columns[0]
        condition_match = re.search(r"(greater than|less than|equals|is|before|after)[\s]*([\w\s]+)", instruction, re.IGNORECASE)

        if not condition_match:
            return "Could not understand the condition. Please use keywords like 'greater than', 'less than', 'equals', 'is', 'before', 'after'."

        condition_type = condition_match.group(1).lower()
        condition_value = condition_match.group(2).strip()

        # Convert condition_value to the appropriate type
        if condition_value.replace('.', '', 1).isdigit():
            condition_value = float(condition_value)
        elif condition_value.lower() in ["true", "false"]:
            condition_value = condition_value.lower() == "true"

        # Convert numeric-like columns to numeric type
        if pd.api.types.is_numeric_dtype(df[column]) or df[column].apply(lambda x: str(x).replace('.', '', 1).isdigit()).all():
            df[column] = pd.to_numeric(df[column], errors='coerce')

        # Filter records based on the condition
        if condition_type in ["greater than", "after"]:
            filtered_df = df[df[column] > condition_value]
        elif condition_type in ["less than", "before"]:
            filtered_df = df[df[column] < condition_value]
        elif condition_type in ["equals", "is"]:
            if pd.api.types.is_numeric_dtype(df[column]):
                filtered_df = df[df[column] == condition_value]
            else:
                filtered_df = df[df[column].str.contains(condition_value, case=False, na=False)]
        else:
            return "Condition type not supported for filtering. Please use 'greater than', 'less than', or 'equals'."

        # Debug: Log filtered DataFrame state
        # st.write("Filtered DataFrame preview:")
        # st.write(filtered_df.head())
        return filtered_df
    
        # return "Instruction not recognized."

    except Exception as e:
        st.error(f"Error handling instruction: {e}")
        return f"Error handling instruction: {e}"

def start_periodic_task(interval):
    """Starts the anomaly check task in a separate thread."""
    periodic_thread = threading.Thread(target=run_periodically, args=(interval,))
    periodic_thread.daemon = True  # Ensures the thread exits when the main program exits
    periodic_thread.start()
    print(f"Background task started: running every {interval} seconds.")


# Main function for the Streamlit app

def main():
    # Set up page layout
    st.set_page_config(page_title="Chatbot", layout="wide")

        # .chat-container {
        #     display: flex;
        #     flex-direction: column;
        #     height: 70vh;
        #     overflow-y: auto;
        #     background-color: #f7f7f7;
        #     padding: 10px;
        #     border: 1px solid #ddd;
        #     border-radius: 8px;
        # }

        #  .stForm {
        #     position: fixed;
        #     bottom: 7%;
        #     left: 29%;
        #     width:69%;
        #     border: 0;
        #     z-index: 1000;
        # }
    st.markdown(
        """
        <style>

        .chat-message {
            margin: 10px 0;
            padding: 10px;
            border-radius: 8px;
            max-width: 60%;
        }
        .user-message {
            //align-self: flex-start;
            background-color: #0084ff;
            color: white;
            //margin-left: 300px;
            margin-left: 40%;
        }
        .bot-message {
            //align-self: flex-end;
            background-color: #e4e6eb;
            color: #232324;
            margin-right: 10px;
        }


        .stForm {
            position: fixed;
            bottom: 5%; /* Adjusted to make it more balanced */
            left: 60%; /* Center the form */
            transform: translateX(-50%); /* Center alignment */
            width: 70%; /* Responsive width */
            max-width: 800px; /* Optional: limit the max width */
            border: 0;
            z-index: 1000; /* Make sure it appears on top */
            # background-color: #f7f7f7;
            background-color: #a8a7a7;
            border-radius: 8px; /* Optional: rounded corners */
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2); /* Optional: add shadow */
        }

        @media screen and (max-width: 1024px) {
            .stForm {
                width: 90%; /* Adjust width for tablets and smaller desktop views */
            }
        }

        @media screen and (max-width: 768px) {
            .stForm {
                width: 100%; /* Full width for mobile devices */
                left: 0; /* Align to the left side */
                transform: translateX(0); /* No centering */
            }
        }

        
        input[class]{
            font-size:80%;
            # color: white;
            color: #232324;
            # background-color: #deddd9;
            
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Sidebar for file selection
    current_wd = os.getcwd()
    sheet_folder_path = f"{current_wd}/files/sheets"
    csv_files = [f for f in os.listdir(sheet_folder_path) if f.endswith('.csv')]
    csv_files.sort()

    st.sidebar.header("File Selection")
    selected_file = st.sidebar.selectbox("Select a CSV file:", csv_files)
    df = None
    file_path = None
    if selected_file:
        file_path = f'{sheet_folder_path}/{selected_file}'
        df = load_csv(file_path)

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    # Display chat history
    with st.container(border=True):
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        for msg in st.session_state["messages"]:
            if msg["type"] == "text":
                sender_class = "bot-message" if msg["sender"] == "bot" else "user-message"
                st.markdown(
                    f'<div class="chat-message {sender_class}">{msg["content"]}</div>',
                    unsafe_allow_html=True,
                )
            elif msg["type"] == "dataframe":
                st.write("### Response:")
                st.dataframe(msg["content"], use_container_width=True)
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Input box at the bottom
    with st.form("chat_input_form", clear_on_submit=True):
        user_input = st.text_input("Type your query:", "", key="chat_input", label_visibility="hidden", placeholder="Type your query")
        submitted = st.form_submit_button("Send")
    # Handle user input and bot response
    if submitted and user_input.strip():
        # Add user message to chat history
        st.session_state["messages"].append({"sender": "user", "type": "text", "content": user_input})

        if df is None:
            bot_response = "Please select a file before querying."
            st.session_state["messages"].append({"sender": "bot", "type": "text", "content": bot_response})
        else:
            # Call query handling logic
            result = handle_instruction(user_input, df, file_path)
            if isinstance(result, pd.DataFrame):
                st.session_state["messages"].append({"sender": "bot", "type": "dataframe", "content": result})
            else:
                st.session_state["messages"].append({"sender": "bot", "type": "text", "content": result})

        # Refresh to display the new message
        st.rerun()


if __name__ == "__main__":
    # start_periodic_task(3600)  # Runs every 1 hour
    main()
