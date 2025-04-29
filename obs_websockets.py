import time
import sys
import os
from obswebsocket import obsws, requests  # noqa: E402
from websockets_auth import WEBSOCKET_HOST, WEBSOCKET_PORT, WEBSOCKET_PASSWORD

##########################################################
##########################################################

class OBSWebsocketsManager:
    ws = None
    
    def __init__(self):
        # Connect to websockets
        self.ws = obsws(WEBSOCKET_HOST, WEBSOCKET_PORT, WEBSOCKET_PASSWORD)
        try:
            self.ws.connect()
        except:
            print("\nPANIC!!\nCOULD NOT CONNECT TO OBS!\nDouble check that you have OBS open and that your websockets server is enabled in OBS.")
            time.sleep(10)
            sys.exit()
        print("Connected to OBS Websockets!\n")

    def disconnect(self):
        self.ws.disconnect()


    # Set the current scene
    def set_scene(self, new_scene):
        self.ws.call(requests.SetCurrentProgramScene(sceneName=new_scene))

    # Set the visibility of any source's filters
    def set_filter_visibility(self, source_name, filter_name, filter_enabled=True):
        self.ws.call(requests.SetSourceFilterEnabled(sourceName=source_name, filterName=filter_name, filterEnabled=filter_enabled))

    # Set the visibility of any source
    def set_source_visibility(self, scene_name, source_name, source_visible=True):
        response = self.ws.call(requests.GetSceneItemId(sceneName=scene_name, sourceName=source_name))
        print(f"Response: {response.datain}")  # Print the response to see its structure
    
        if 'sceneItemId' not in response.datain:
            print("Error: 'sceneItemId' not found in response.")
            return
    
        myItemID = response.datain['sceneItemId']
        self.ws.call(requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=myItemID, sceneItemEnabled=source_visible))

    # Returns the current text of a text source
    def get_text(self, source_name):
        response = self.ws.call(requests.GetInputSettings(inputName=source_name))
        return response.datain["inputSettings"]["text"]

    # Returns the text of a text source
    def set_text(self, source_name, new_text):
        self.ws.call(requests.SetInputSettings(inputName=source_name, inputSettings = {'text': new_text}))

    def get_source_transform(self, scene_name, source_name):
        response = self.ws.call(requests.GetSceneItemId(sceneName=scene_name, sourceName=source_name))
        myItemID = response.datain['sceneItemId']
        response = self.ws.call(requests.GetSceneItemTransform(sceneName=scene_name, sceneItemId=myItemID))
        transform = {}
        transform["positionX"] = response.datain["sceneItemTransform"]["positionX"]
        transform["positionY"] = response.datain["sceneItemTransform"]["positionY"]
        transform["scaleX"] = response.datain["sceneItemTransform"]["scaleX"]
        transform["scaleY"] = response.datain["sceneItemTransform"]["scaleY"]
        transform["rotation"] = response.datain["sceneItemTransform"]["rotation"]
        transform["sourceWidth"] = response.datain["sceneItemTransform"]["sourceWidth"] # original width of the source
        transform["sourceHeight"] = response.datain["sceneItemTransform"]["sourceHeight"] # original width of the source
        transform["width"] = response.datain["sceneItemTransform"]["width"] # current width of the source after scaling, not including cropping. If the source has been flipped horizontally, this number will be negative.
        transform["height"] = response.datain["sceneItemTransform"]["height"] # current height of the source after scaling, not including cropping. If the source has been flipped vertically, this number will be negative.
        transform["cropLeft"] = response.datain["sceneItemTransform"]["cropLeft"] # the amount cropped off the *original source width*. This is NOT scaled, must multiply by scaleX to get current # of cropped pixels
        transform["cropRight"] = response.datain["sceneItemTransform"]["cropRight"] # the amount cropped off the *original source width*. This is NOT scaled, must multiply by scaleX to get current # of cropped pixels
        transform["cropTop"] = response.datain["sceneItemTransform"]["cropTop"] # the amount cropped off the *original source height*. This is NOT scaled, must multiply by scaleY to get current # of cropped pixels
        transform["cropBottom"] = response.datain["sceneItemTransform"]["cropBottom"] # the amount cropped off the *original source height*. This is NOT scaled, must multiply by scaleY to get current # of cropped pixels
        return transform

    # The transform should be a dictionary containing any of the following keys with corresponding values
    # positionX, positionY, scaleX, scaleY, rotation, width, height, sourceWidth, sourceHeight, cropTop, cropBottom, cropLeft, cropRight
    # e.g. {"scaleX": 2, "scaleY": 2.5}
    # Note: there are other transform settings, like alignment, etc, but these feel like the main useful ones.
    # Use get_source_transform to see the full list
    def set_source_transform(self, scene_name, source_name, new_transform):
        response = self.ws.call(requests.GetSceneItemId(sceneName=scene_name, sourceName=source_name))
        myItemID = response.datain['sceneItemId']
        self.ws.call(requests.SetSceneItemTransform(sceneName=scene_name, sceneItemId=myItemID, sceneItemTransform=new_transform))

    # Note: an input, like a text box, is a type of source. This will get *input-specific settings*, not the broader source settings like transform and scale
    # For a text source, this will return settings like its font, color, etc
    def get_input_settings(self, input_name):
        return self.ws.call(requests.GetInputSettings(inputName=input_name))

    # Get list of all the input types
    def get_input_kind_list(self):
        return self.ws.call(requests.GetInputKindList())

    # Get list of all items in a certain scene
    def get_scene_items(self, scene_name):
        return self.ws.call(requests.GetSceneItemList(sceneName=scene_name))


if __name__ == '__main__':

    print("Connecting to OBS Websockets")
    obswebsockets_manager = OBSWebsocketsManager()

    print("Changing visibility on a source \n\n")
    obswebsockets_manager.set_source_visibility('*** Mid Monitor', "Window Capture", False)
    time.sleep(3)
    obswebsockets_manager.set_source_visibility('*** Mid Monitor', "Window Capture", True)
    time.sleep(3)

    print("\nEnabling filter on a scene...\n")
    time.sleep(3)
    obswebsockets_manager.set_filter_visibility("/// TTS Characters", "Move Source - Godrick - Up", True)
    time.sleep(3)
    obswebsockets_manager.set_filter_visibility("/// TTS Characters", "Move Source - Godrick - Down", True)
    time.sleep(5)

    print("Swapping scene!")
    obswebsockets_manager.set_scene('*** Camera (Wide)')
    time.sleep(3)
    print("Swapping back! \n\n")
    obswebsockets_manager.set_scene('*** Mid Monitor')


    print("Getting a text source's current text! \n\n")
    current_text = obswebsockets_manager.get_text("??? Challenge Title ???")
    print(f"Here's its current text: {current_text}\n\n")

    print("Changing a text source's text! \n\n")
    obswebsockets_manager.set_text("??? Challenge Title ???", "Here's my new text!")
    time.sleep(3)
    obswebsockets_manager.set_text("??? Challenge Title ???", current_text)
    time.sleep(1)

    response = obswebsockets_manager.get_input_settings("??? Challenge Title ???")
    print(f"\nHere are the input settings:{response}\n")
    time.sleep(2)

    response = obswebsockets_manager.get_input_kind_list()
    print(f"\nHere is the input kind list:{response}\n")
    time.sleep(2)

    response = obswebsockets_manager.get_scene_items('*** Mid Monitor')
    print(f"\nHere is the scene's item list:{response}\n")
    time.sleep(2)

    time.sleep(30)

    
def test_display_image():
    # Create an instance of OBSWebsocketsManager
    obs_manager = OBSWebsocketsManager()

    # Define the name of the image source and scene
    scene_name = "*** Mid Monitor"  # Replace with your actual scene name
    source_name = "Madeira Flag"  # Replace with the actual source name in OBS
    
    # Check if the image file exists
    image_path = os.path.join(os.getcwd(), "Madeira Flag")
    if not os.path.exists(image_path):
        print(f"Image file 'Img_01' not found in {os.getcwd()}. Please ensure the image is present.")
        return

    # List all sources in the scene to check if the image source is loaded
    print(f"Listing all sources in scene '{scene_name}'...")
    response = obs_manager.ws.call(requests.GetSceneItemList(sceneName=scene_name))
    print(f"Response: {response.datain}")  # See what sources are available

    # Check if the source exists in the scene
    if source_name not in [item['sourceName'] for item in response.datain.get('sceneItems', [])]:
        print(f"Source '{source_name}' not found in scene '{scene_name}'. Please ensure the source is part of the scene.")
        return

    # Set the visibility of the image to True (show it on the screen)
    print("Displaying the image for 10 seconds...")
    obs_manager.set_source_visibility(scene_name, source_name, True)

    # Wait for 10 seconds
    time.sleep(10)

    # Set the visibility of the image to False (hide it after 10 seconds)
    print("Hiding the image...")
    obs_manager.set_source_visibility(scene_name, source_name, False)

    # Disconnect from OBS WebSockets
    obs_manager.disconnect()

# Run the test
if __name__ == "__main__":
    test_display_image()


#############################################