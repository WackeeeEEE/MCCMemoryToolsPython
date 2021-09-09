from ctypes.wintypes import HANDLE
import cv2
import numpy as np
import json
import os
import MEMORY
import asyncio
import time

imgName = "centerOfClip_marked.PNG"
img = cv2.imread(imgName)

# Load Offset Config
imgOffsetFile = open("imgOffsets.json", "r+")
imgOffsetData = json.load(imgOffsetFile)
imgOffsetFile.close()

playerOffsetFile = open("playerOffsets.json", "r+")
playerOffsetData = json.load(playerOffsetFile)
playerOffsetFile.close()


# Create ImageOffsets class
class ImageOffsets:
	def __init__(self):
		self.name = imgName
		#self.scale = imgOffsetData[imgName]["scale"]
		self.start_x = imgOffsetData[imgName]["start_x"]
		self.center_x = imgOffsetData[imgName]["center_x"]
		self.end_x = imgOffsetData[imgName]["end_x"]
		self.start_y = imgOffsetData[imgName]["start_y"]
		self.center_y = imgOffsetData[imgName]["center_y"]
		self.end_y = imgOffsetData[imgName]["end_y"]
	def update(self):
		self.__init__()

# Define Starting Clip Position (for scaling coordinates to image)
CLIP_START_X = -22.715
CLIP_START_Y = 29.927

CLIP_END_X = -30.685
CLIP_END_Y = 3.3

# Define Window Parameters

# Intended window resolution/scale (not needed anymore, using dynamic res calc)
WIN_RES_X = 241
WIN_RES_Y = 726

# Image Margins (extra pixels beyond start & end)
IMG_MARGIN_X = 20
IMG_MARGIN_Y = 20

# Window Padding to make sure everything is presented (not needed anymore, i'm dumb)
WIN_PAD_X = 89
WIN_PAD_Y = 200

# Instantiate imgOffsets for current reference image
imgOffsets = ImageOffsets()

#print(f"name: {imgOffsets.name}\nx: {imgOffsets.start_x}\ny: {imgOffsets.start_y}")

# Define shifting image to match window
def shift_img(img, imgOffsets):
	img_rows, img_cols = img.shape[:2]
	#translation_matrix = np.float32([ [1, 0, (-1 * imgOffsets.start_x - IMG_MARGIN_X - WIN_PAD_X) ], [0, 1, (-1 * imgOffsets.start_y - IMG_MARGIN_Y - WIN_PAD_Y) ] ])
	translation_matrix = np.float32([ [1, 0, (-1 * imgOffsets.end_x) + IMG_MARGIN_X ], [0, 1, (-1 * imgOffsets.start_y) + IMG_MARGIN_Y ] ])
	shiftedImg = cv2.warpAffine(img, translation_matrix, (img_cols, img_rows))
	return shiftedImg

# Logic to convert between pixels and ingame coords
def coordsToPixels( playerCoords, imgScale): # 0 and 1 are ingame coords, x and y are pixels
	x = int( ( ( IMG_MARGIN_X * imgScale ) - (CLIP_END_X - playerCoords[0] ) ) / imgScale )
	y = int( ( ( IMG_MARGIN_Y * imgScale ) + (CLIP_START_Y - playerCoords[1] ) ) / imgScale )
	#print(f"IGC: {playerCoords[0]}, {playerCoords[1]}\nPx: {x}, {y}")
	return (x,y)

# print(f"Scale: {imgScale}")
# leftMarginPx = 20 * imgScale

async def updateMap():
	global playerDot, shiftedImg
	playerCoords = await getPlayerPosition()
	playerPx = coordsToPixels(playerCoords, imgScale)
	cv2.circle(playerDot, playerPx, 2, (0, 255, 0), -1)
	cv2.imshow(windowName, playerDot)

async def clearMap():
	global playerDot, shiftedImg
	print("CLEARING MAP!!!\nCLEARING MAP!!!\nCLEARING MAP!!!\nCLEARING MAP!!!")
	playerCoords = await getPlayerPosition()
	playerPx = coordsToPixels(playerCoords, imgScale)
	playerDot = shiftedImg.copy()

async def getPlayerPosition():
	playerX = await MEMORY.mcc.h3xposWatcher.getCurrentValue()
	playerY = await MEMORY.mcc.h3yposWatcher.getCurrentValue()
	return (playerX, playerY)

async def mainLoop():
	# Create cv2 window
	global windowName, img, shiftedImg, playerDot, imgScale
	windowName = f"Silo Clip Viewer - {imgOffsets.name}"
	cv2.namedWindow(windowName, cv2.WINDOW_AUTOSIZE)
	img = cv2.imread(imgName)
	shiftedImg = shift_img(img, imgOffsets)
	imgScale = (CLIP_START_X - CLIP_END_X) / (imgOffsets.start_x - imgOffsets.end_x)

	#playerDot = cv2.circle(shiftedImg, ((imgOffsets.start_x - imgOffsets.end_x) + IMG_MARGIN_X, int(IMG_MARGIN_Y / 2)), 2, (0, 255, 0), -1)

	playerPx = coordsToPixels(await getPlayerPosition(), imgScale)
	playerDot = shiftedImg.copy()
	cv2.circle(playerDot, playerPx, 2, (0, 255, 0), -1)
	cv2.imshow(windowName, playerDot)
	cv2.resizeWindow(windowName, (imgOffsets.start_x - imgOffsets.end_x) + 2 * IMG_MARGIN_X, (imgOffsets.end_y - imgOffsets.start_y) + 2 * IMG_MARGIN_Y) # adding margins to window resolution

	# Main Logic
	lastTick = 0
	while True:
		tick = await MEMORY.mcc.h3igtWatcher.getCurrentValue()
		#print(len(MEMORY.mcc.proc.tHandles))
		if lastTick < tick:
			MEMORY.mcc.proc.suspend()
			print(f"suspended execution, tick: {tick}")
			print(f"resuming execution")
			MEMORY.mcc.proc.resume()
			if tick - lastTick == 1:
				print("correctly captured next tick")
			if tick - lastTick == 2:
				print("NOT CAPTURING EVERY TICK")
		
		if lastTick == tick:
			#print(f"game is still on tick {tick}")
			pass

		if lastTick > tick:
			print("tickback detected, resetting map")
			await clearMap()
		await updateMap()

		lastTick = tick
		if cv2.waitKey(16) & 0xFF == ord('1'):
			break

asyncio.run(mainLoop())
cv2.destroyAllWindows()

#241, 726
#300, 7

#cv2.imshow()
#cv2.waitKey(16)

# width = 100
# height = 100

# # Make empty black image of size (100,100)
# img = np.zeros((height, width, 3), np.uint8)

# red = [0,0,255]

# # Change pixel (50,50) to red
# img[50,50] = red

# cv2.imshow('img', img)
# cv2.waitKey(0)


_reference = """
-22.715 29.927 -4.638 / 70.28 -85.50 / 1.000
-22.715 = 660px - x
29.927 = 85px - y
-30.685 = 450px - endx
3.373 = 765px - endy



autoaimed to / 71.63  

-30.685 3.373 -6.280 / 1.000

-26.7 16.65 -5.459

<CheatEntry>
	  <ID>25948</ID>
	  <Description>"h3 x pos"</Description>
	  <VariableType>Float</VariableType>
	  <Address>"halo3.dll"+01164BEC</Address>
	  <Offsets>
		<Offset>4</Offset>
	  </Offsets>
	</CheatEntry>
	<CheatEntry>
	  <ID>25949</ID>
	  <Description>"h3 y pos"</Description>
	  <VariableType>Float</VariableType>
	  <Address>"halo3.dll"+01164BEC</Address>
	  <Offsets>
		<Offset>8</Offset>
	  </Offsets>
	</CheatEntry>
	<CheatEntry>
	  <ID>25950</ID>
	  <Description>"h3 z pos"</Description>
	  <VariableType>Float</VariableType>
	  <Address>"halo3.dll"+01164BEC</Address>
	  <Offsets>
		<Offset>C</Offset>
	  </Offsets>
	</CheatEntry>
	<CheatEntry>
	  <ID>25945</ID>
	  <Description>"h3 x vel"</Description>
	  <VariableType>Float</VariableType>
	  <Address>"halo3.dll"+01164BEC</Address>
	  <Offsets>
		<Offset>44</Offset>
	  </Offsets>
	</CheatEntry>
	<CheatEntry>
	  <ID>25946</ID>
	  <Description>"h3 y vel"</Description>
	  <VariableType>Float</VariableType>
	  <Address>"halo3.dll"+01164BEC</Address>
	  <Offsets>
		<Offset>48</Offset>
	  </Offsets>
	</CheatEntry>
	<CheatEntry>
	  <ID>25947</ID>
	  <Description>"h3 z vel"</Description>
	  <VariableType>Float</VariableType>
	  <Address>"halo3.dll"+01164BEC</Address>
	  <Offsets>
		<Offset>4C</Offset>
	  </Offsets>
	</CheatEntry>
	"""