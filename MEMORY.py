from ctypes import *
import ctypes
from ctypes.wintypes import *
import psutil

from struct import *

import json
from types import SimpleNamespace

import asyncio
import time

k32 = windll.kernel32

openProc = k32.OpenProcess
createToolhelp32Snapshot = k32.CreateToolhelp32Snapshot
thread32First = k32.Thread32First
thread32Next = k32.Thread32Next
CloseHandle = k32.CloseHandle
openProc.argtypes = [DWORD, BOOL, DWORD]
openProc.restype = HANDLE

readProcMem = k32.ReadProcessMemory
readProcMem.argtypes = [HANDLE, LPCVOID, LPVOID, c_size_t, POINTER(c_size_t)]
readProcMem.restype = BOOL

writeProcMem = k32.WriteProcessMemory
writeProcMem.argtypes = [HANDLE, LPVOID, LPCVOID, c_size_t, POINTER(c_size_t)]

psapi = windll.psapi
psapi.GetModuleFileNameExA.argtypes = [HANDLE, HMODULE, LPSTR, DWORD]
psapi.GetModuleFileNameExA.restype = BOOL

# Attempt at suspension functions
suspendThread = k32.SuspendThread
resumeThread = k32.ResumeThread

def suspend(tHandle):
    ret = suspendThread(tHandle)
    print(ret, type(ret))
    if ret == -1:
        print(f"ERROR: {GetLastError()}\n{FormatError(GetLastError())}")

def resume(tHandle):
    ret = resumeThread(tHandle)
    print(ret, type(ret))
    if ret == -1:
        print(f"ERROR: {GetLastError()}\n{FormatError(GetLastError())}")


nameProcess = "MCC-Win64-Shipping.exe"
playerOffsets = json.load(open("playerOffsets.json", "r"), object_hook=lambda d: SimpleNamespace(**d)) # might wanna change this, namespace stuff scary
strToType = {
    "string":str(),
    "int":int(),
    "float":float()
}

gameOffsets = json.load(open("pointers.json", "r"), object_hook=lambda d: SimpleNamespace(**d))

PROCESS_VM_READ = 0x0010 # READ-ONLY
PROCESS_ALL_ACCESS = 0x1F0FFF # MORE_ACCESS
PROCESS_QUERY_INFORMATION = 0x0400

THREAD_ALL_ACCESS = 0x0002
TH32CS_SNAPTHREAD = 0x00000004

class THREADENTRY32(ctypes.Structure): # Yoined from https://code.activestate.com/recipes/576362-list-system-process-and-process-information-on-win/
    _fields_ = [
        ('dwSize' , c_long ),
        ('cntUsage' , c_long),
        ('th32ThreadID' , c_long),
        ('th32OwnerProcessID' , c_long),
        ('tpBasePri' , c_long),
        ('tpDeltaPri' , c_long),
        ('dwFlags' , c_long) ]

def listProcessThreads( ProcessID ):
    hThreadSnap = c_void_p(0)
    te32 = THREADENTRY32()
    te32.dwSize = sizeof(THREADENTRY32)

    hThreadSnap = createToolhelp32Snapshot( TH32CS_SNAPTHREAD, 0 )

    ret = thread32First( hThreadSnap, pointer(te32) )

    if ret == 0 :
        print(f'ListProcessThreads() Error on Thread32First[{GetLastError()}]')
        CloseHandle( hThreadSnap )
        return False

    tHandles = {}
    while ret :
        if te32.th32OwnerProcessID == ProcessID : 
            tHandles[te32.th32ThreadID] = te32.tpBasePri
        ret = thread32Next( hThreadSnap, pointer(te32) )
    CloseHandle( hThreadSnap )
    return tHandles

# def findThreads(pid):
#     print(pid)
#     tHandle = -1
#     threadListHandle = createToolhelp32Snapshot(TH32CS_SNAPTHREAD, pid)
#     te32 = TE32C()
#     return tHandle

# Fun starts here

class ModuleInformation:
    def __init__(self, index, name, path, address):
        self.index = index
        self.name = name
        self.path = path
        self.address = address

class Process:
    def __init__(self, pid, name):
        self.pid = pid
        self.handle = openProc(PROCESS_ALL_ACCESS, False, self.pid)
        self.mods = getModules(self.handle)
        self.name = name
        self.address = None
        for mod in self.mods:
            if mod.name == self.name:
                self.address = mod.address
        if self.address == None:
            print("PROCESS ADDRESS NOT FOUND")
        else:
            print(f"Process {self.name} found at {self.address}")
        #findThreads(self.pid)
        #self.tHandle = 0
        self.tHandles = listProcessThreads(self.pid)



    def readP(self, address, size):#, datatype=None): # size bytes
        buffer = create_string_buffer(size)
        counter = c_ulonglong()
        a = readProcMem(self.handle, address, buffer, size, byref(counter))
        if a == 0:
            print(f"ERROR: {GetLastError()}\n{FormatError(GetLastError())}")
        else:
            return Fragment(address, buffer.raw) #data

    def readDeepP(self, deepPointer, size, datatype=None):
        pt = self.readP(self.address+deepPointer[0], 8).asPtr()
        for offset in deepPointer[1:-1]:
            pt = self.readP(pt+offset, 8).asPtr()
        data = self.readP(pt+deepPointer[-1], size)
        if datatype != None: # might implement this on the next highest level, not sure yet - ex: data return will be as"Type"()
            if type(datatype) == type(int()):
                #print(f"as type {type(datatype)}: {data.asInt()}")
                if len(data.raw) == 4:
                    return data.asInt32()
            if type(datatype) == type(str()):
                #print(f"as type {type(datatype)}: {data.asStr()}")
                return data.asStr()
            if type(datatype) == type(float()):
                #print(f"as type {type(datatype)}: {data.asFloat()}")
                return data.asFloat()
            # if type(datatype) == type(ptr()): #eeeeeeeh, do i have to?
            #     print("as type {type(datatype)}: {data.asPtr()}")
        return data



    def suspend(self):
        suspendThread(self.tHandle)

    def resume(self):
        resumeThread(self.tHandle)

    def listModules(self, key=None):
        for mod in self.mods:
            if key == None:
                print(f"Index: {mod.index} | Name: {mod.name} | Address: {mod.address}")
            else:
                if mod.name == key:
                    print(f"Index: {mod.index} | Name: {mod.name} | Address: {mod.address}")


    ### Testy Stuff ###

    def printLevel(self):
        level = playerOffsets.halo1.level
        #levelPointer = Pointer(level.offsets, level.length, level.type)# shorten
        levelPointer = PointerShort(level)
        levelFragment = self.readDeepP(levelPointer.offsets, levelPointer.length, levelPointer.type)
        # print(f"Current level: {levelFragment.asStr()}")

class Fragment:
    def __init__(self, address, raw):
        self.address = address
        self.raw = raw
        self.size = len(self.raw)
        
    def __doc__():
        return "Arbitrarily sized block of process data"
    def asInt(self):
        return unpack("<Q", self.raw)[0]
    def asInt32(self):
        return unpack("<i", self.raw)[0]
    def asStr(self):
        return self.raw.decode('utf-8')
    def asFloat(self):
        return unpack("<f", self.raw)[0]
    def asDouble(self):
        return unpack("<d", self.raw)[0]
    def asPtr(self): #kinda just for clarity, dont think i really need
        return unpack("<Q", self.raw)[0]

class Pointer:
    def __init__(self, offsets, length, type): # list/tuple in

        self.offsets = [] # converting string hex/int? to int
        for offset in offsets:
            self.offsets.append(int(offset, 0)) # using 0 base to invoke guessing base, useful for different types in db?

        self.length = length
        self.type = strToType[type]

class PointerShort:
    def __init__(self, pointerObj): # composite arg in

        self.offsets = [] # converting string hex/int? to int
        for offset in pointerObj.offsets:
            self.offsets.append(int(offset, 0)) # using 0 base to invoke guessing base, useful for different types in db?

        self.length = pointerObj.length
        self.type = strToType[pointerObj.type]

class Governor:
    def __init__(self):
        self.objects = []
        self.timeframes = []
        self.fpsWatcher = WatcherFPS()
        

    async def ready(self, obj):
        if time.time() >= obj.lastRun+obj.interval:
            obj.run()
            self.timeframes.append(time.time())

    def addWatcher(self, obj):
        self.objects.append(obj)

    def listWatchers(self):
        watcherStr = str('\n'.join([obj.name for obj in self.objects]))
        print(f"Current Watchers:{watcherStr}")

    async def fps(self):
        counter = 0
        if time.time() > self.fpsWatcher.lastRun + self.fpsWatcher.interval:
            self.fpsWatcher.lastRun = time.time()
            if len(self.timeframes) > 500:
                for timeframe in reversed(self.timeframes):
                    if time.time() < timeframe + 1:
                        counter += 1
                # for object in self.objects:
                #     print(object.val)
                print(f"Reading game memory at {counter} frames per second")

    def objectData(self, watcherName):
        return filter(lambda x:x.name == watcherName, self.objects)[0].val

    async def loop(self):
        while True:
            for obj in self.objects:
                await self.ready(obj)
            await self.fps()


class Watcher:
    def __init__(self, proc, pointer, name, interval=1):
        self.proc = proc
        self.pointer = pointer
        self.name = name
        self.interval = interval
        self.lastRun = time.time()
        self.run()

    def run(self):
        self.val = self.proc.readDeepP(self.pointer.offsets, self.pointer.length, datatype=self.pointer.type)
        #print(self.val)
        self.lastRun = time.time()
        return self.val

    async def getCurrentValue(self):
        self.run()
        return self.val
   
## to mess with async behavior
# class testCounter: 
#     def __init__(self, initial):
#         self.count = initial

#     def increment(self):
#         self.count += 1
#         self.output()

#     def output(self):
#         print(f"Current count: {self.count}")


class WatcherFPS:
    def __init__(self):
        self.interval = 5
        self.lastRun = time.time()

# class Phone:
#     def __init__(self, string):
#         self.string = string
    
#     def __repr__(self) -> str:
#         return self.string

def getPIDs(nameProcess):
    found = []
    for proc in psutil.process_iter():
        if str(nameProcess) in str(proc.name):
            print("FOUND", nameProcess)
            found.append(proc.pid)
    try:
        if len(found) > 0:
            return found
    except Exception as e:
        print(type(e), e)
        return None

def getProc(pid):

    # Get a handle to the process
    proc = openProc( (PROCESS_VM_READ | PROCESS_QUERY_INFORMATION) , False, pid)
    if proc == 0:
        print(f"ERROR: {GetLastError()}\n{FormatError(GetLastError())}")
    else:
        return proc

def getModules(proc):

    # Get a handle to the process
    hProcess = proc

    # Set up vars
    arr = HMODULE * 1024
    hMods = arr() 
    cbNeeded = c_ulong()
    modNameArray = c_char * MAX_PATH
    clearName = modNameArray()
    szModName = modNameArray()

    # Get a list of all the modules in this process
    EnumAttempt = psapi.EnumProcessModules(hProcess, hMods, sizeof(hMods), byref(cbNeeded))
    if EnumAttempt == 0:
        print(GetLastError())
    else:
        mods = []

        for i, val in enumerate(hMods[:int(cbNeeded.value / sizeof(HMODULE))]):
            memmove(byref(szModName), byref(clearName), sizeof(clearName))
            if val != None:
                modAttempt = psapi.GetModuleFileNameExA(hProcess, val, szModName, int(sizeof(szModName) / sizeof(c_char)))
                if modAttempt == 0:
                    print(GetLastError())
                else:
                    index = i
                    name = str(b''.join([i for i in szModName if i != b'\x00'])).split("\\")[-1][:-1]
                    path = str(b''.join([i for i in szModName if i != b'\x00']))[2:-1]
                    address = val
                    mods.append(ModuleInformation(index, name, path, address))
            else:
                pass
        return mods

def printModules(pid, proc):

    print(f"Modules of process {pid}:")
    proc = getProc(pid)
    mods = getModules(proc)

    for mod in mods:
        print(f"Index: {mod.index}\nModule: {mod.name}\nVirtual Address: {mod.address}")

def create_handle(nameProcess):
    PIDs = getPIDs(nameProcess)
    if type(PIDs) == type(None):
        print(f"Process {nameProcess} not found")
        proc = None
    else:
        print(f"{len(PIDs)} Processes found, acting on first PID - {PIDs[0]}")
        print(PIDs)
        proc = Process(PIDs[0], nameProcess)
        #print(f"Handle:{proc.handle} | Type: {type(proc.handle)}")
    return proc

class Root:
    def __init__(self):
        self.proc = create_handle(nameProcess)
        #g = Governor()
        
        self.h3xpos = playerOffsets.halo3.xpos
        self.h3xposWatcher = Watcher(self.proc, PointerShort(self.h3xpos), name="h3xpos", interval=.005)
        self.h3ypos = playerOffsets.halo3.ypos
        self.h3yposWatcher = Watcher(self.proc, PointerShort(self.h3ypos), name="h3ypos", interval=.005)
        self.h3igt = gameOffsets.halo3.igt2
        self.h3igtWatcher = Watcher(self.proc, PointerShort(self.h3igt), name="h3igt", interval=.005)

mcc = Root()
