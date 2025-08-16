# MergeTacticsBot By Eric Berg

Welcome to the Merge Tactics Bot repository!
This repository is a documentation of my work in creating a Merge Tactics simulator and a Reinforcement Learning bot to play it

## What you need to do:
- Install requirements
- Customise one of the bots
- Run!

  ```python
  # Edit these or build your own!
  def greedy_bot_logic(player, round_number):
  def efficient_bot_logic(player, round_number):
  def combo_seeker_bot_logic(player, round_number):
  def random_bot_logic(player, round_number):
  ```
## What all the files do
frame_splitter: takes an input video and splits it up into every nth frame
main_sim: merge tactics simulator main functionality
mapping_fixer: takes two yolo annotations and standardises them so they can be merged together
test.py: displays a test image to see if training model is accurate
train.py: yolo training function
xml_to_yolo: takes an annotations.xml from cvat (cvat images export) and converts to useable yolo format
yolo_to_xml: runs the model we trained on a bunch of images and exports the annotations out in xml to be put into cvat for fixing
