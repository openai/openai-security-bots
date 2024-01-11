import os
import pickle


class Database:
    """
    This class represents a database for storing user messages.
    The data is stored in a pickle file.
    """

    def __init__(self):
        """
        Initialize the database. Load data from the pickle file if it exists,
        otherwise create an empty dictionary.
        """
        current_dir = os.path.dirname(os.path.realpath(__file__))
        self.file_path = os.path.join(current_dir, "data.pkl")
        self.data = {}

    def _load_data(self):
        """
        Load data from the pickle file if it exists,
        otherwise return an empty dictionary.
        """
        if os.path.exists(self.file_path):
            with open(self.file_path, "rb") as f:
                return pickle.load(f)
        else:
            return {}

    def _save(self):
        """
        Save the current state of the database to the pickle file.
        """
        with open(self.file_path, "wb") as f:
            pickle.dump(self.data, f)

    # Add a new entry to the database
    def add(self, user_id, message_ts):
        """
        Add a new entry to the database. If the user_id already exists,
        update the message timestamp. Otherwise, create a new entry.
        """
        self.data = self._load_data()
        self.data.setdefault(user_id, {})["message_ts"] = message_ts
        self._save()

    # Delete an entry from the database
    def delete(self, user_id):
        """
        Delete an entry from the database using the user_id as the key.
        """
        self.data = self._load_data()
        self.data.pop(user_id, None)
        self._save()

    # Check if user_id exists in the database
    def user_exists(self, user_id):
        """
        Check if the user_id exists in the database.
        """
        self.data = self._load_data()
        return user_id in self.data

    # Return the message timestamp for a given user_id
    def get_ts(self, user_id):
        """
        Return the message timestamp for a given user_id.
        """
        self.data = self._load_data()
        return self.data[user_id]["message_ts"]

    # Return the user_id given a message_ts
    def get_user_id(self, message_ts):
        """
        Return the user_id given a message_ts.
        """
        self.data = self._load_data()
        for user_id, data in self.data.items():
            if data["message_ts"] == message_ts:
                return user_id
        return None
