import os
from place_order import get_TDsession
import config


# TD accessa nd refresh tokens will be generated
Session = get_TDsession()

# create folders and files
if not os.path.exists(config.data_dir):
    os.mkdir(config.data_dir)
    
config.portfolio_fname