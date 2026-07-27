import pandas as pd
from datetime import datetime, timedelta
import requests
import json
import os
import sys
import logging
import time
import timeit
import csv
import pickle
from dateutil.relativedelta import relativedelta
import urllib.parse

if __name__ == '__main__':
    # Create necessary files and directories
    # Are not overrided by pulling updates
    file_paths = [os.path.join('src', 'register.txt'), os.path.join('src', 'rclone.txt'), os.path.join('ansible', 'hosts.yml')]
    
    for file_path in file_paths:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        if not os.path.exists(file_path):
            with open(file_path, 'w') as file:
                pass  # Create an empty file



    # Run the whole program in a loop
    while True:
        try:
            start = timeit.default_timer()
            src.main.main()
            stop = timeit.default_timer()
            print('Whole Loop Runtime: ', stop - start)
        except Exception as e:
            current_time = time.time()
            error_message = str(e)
            
            if error_message != last_error or (current_time - last_logged_time) > cooldown_period:
                logging.error(f"Exception occured: {e}", exc_info=True)
                last_error = error_message
                last_logged_time = current_time










    