from ctypes.wintypes import BOOLEAN, HANDLE, INT
import numpy as np
import json
import MEMORY
import asyncio
import time
from collections import deque
import struct


#change to H2 input array, igt
playerOffsetFile = open("playerOffsets.json", "r+")
playerOffsetData = json.load(playerOffsetFile)
playerOffsetFile.close()

flyDataFile = open("flyFile.txt", "a+")
flyData = ""
speedBuffer = deque([], maxlen=10)
twentyTicks = deque([], maxlen=20)
twentyState = [False, False, False]
checkingFly = False

def closeOpen():
	global flyDataFile
	flyDataFile.close()
	flyDataFile = open("flyFile.txt", "a+")

def storeFlyAttempt(data):
	global flyData, checkingFly
	checkingFly = True
	flyData = f"{data[0]}, {data[1][0]}, {data[1][1]}\n"
	return

def getInputs(array):
	#incoming array is bytes, no bueno
	newArray = [False, False, False]
	for index, element in enumerate(array):
		if element == 0:
			newArray[index] = False
		else:
			newArray[index] = True
			
	#Clearing cases
	if newArray[0] == True:
		clearStates([0, 1, 2])
	return newArray

def stateTest(recentInputs):
	states = [False, False, False]
	for x in range(3):
		if recentInputs[0][1][x] != recentInputs[1][1][x]:
			if recentInputs[0][1][x] == False:
				states[x] = "ftt" # false to true
			else:
				states[x] = "ttf" # true to false
	return states

def clearStates(indices):
	global twentyState
	for index in indices:
		twentyState[index] = False
		#print(f"clearing {index}")

async def twentyTest(tick, array):
	global twentyState, twentyTicks
	twentyTicks.append((tick, array))
	if len(twentyTicks) < 2:
		return
	else:
		states = stateTest([twentyTicks[-2], twentyTicks[-1]])

		# NORMAL CASES
		if twentyState[0] == False:
			if states[0] == "ttf":
				twentyState[0] = twentyTicks[-1][0]
				clearStates([1, 2])
				print(f"{tick} | Y")
				return
		elif twentyState[1] == False:
			if states[1] == "ftt":
				twentyState[1] = twentyTicks[-1][0]
				clearStates([2])
				print(f"{tick} | X")
				return
		elif twentyState[2] == False:
			if states[2] == "ftt":
				twentyState[2] = twentyTicks[-1][0]
				print(f"{tick} | R")

		await flyCheck(tick)
		return


def parsePos(posBytes):
	split = struct.unpack('<fff', posBytes)
	return split

def checkSpeed(speedBuffer):
	start = speedBuffer[1]
	end = speedBuffer[5]
	vel3d = np.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2 + (end[2] - start[2])**2)
	print(vel3d)
	if vel3d > 0.6:
		isafly = True
	else:
		isafly = False
	return isafly

# Final check
async def flyCheck(tick):
	global twentyState, checkingFly, speedBuffer
	if checkingFly == True:
		pos = parsePos(await MEMORY.mcc.h2posWatcher.getCurrentValue())
		speedBuffer.append(pos)
		if len(speedBuffer) >= 6:
			isafly = checkSpeed(speedBuffer)
			if isafly == True:
				print(f"Congrats, you're FLYING!!")
				flyDataFile.write(flyData)
				closeOpen()
			speedBuffer = []
			checkingFly = False

	if type(twentyState[0]) != bool:
		if type(twentyState[1]) != bool:
			if type(twentyState[2]) != bool:
				print(f"{[twentyState[1] - twentyState[0], twentyState[2] - twentyState[1]]} | Swordfly Attempted")
				storeFlyAttempt([tick, [twentyState[1] - twentyState[0], twentyState[2] - twentyState[1]]])
				clearStates([0, 1, 2]) # clear once fly attempt is finished


async def mainLoop():
	
	# Main Logic

	# Instantiate input stuff
	inputWatcher = MEMORY.mcc.h2inputWatcher

	lastTick = 0
	missedTicks = 0
	while True:
		tick = await MEMORY.mcc.h2igtWatcher.getCurrentValue()
		#print(len(MEMORY.mcc.proc.tHandles))jj
		if lastTick < tick:
			MEMORY.mcc.proc.suspend()
			#print(f"suspended execution on tick {tick} | {suf}")
			if tick - lastTick == 1:
				suf = "1 TICKS"
			elif tick - lastTick == 2:
				suf = "2 TICKS"
				missedTicks += 1
				print(f"Missed Ticks: {missedTicks}")
			else:
				suf = "BAAAAAD"
			await twentyTest(tick, getInputs(await MEMORY.mcc.h2inputWatcher.getCurrentValue()))

			MEMORY.mcc.proc.resume()

		if lastTick == tick:
			#print(f"game is still on tick {tick}")
			pass

		if lastTick > tick:
			print("tickback detected, resetting...")

		lastTick = tick

asyncio.run(mainLoop())
