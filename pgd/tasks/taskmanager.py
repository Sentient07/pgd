from tasks import *

""" TaskManager - Class that tracks and controls tasks
"""
class TaskManager():

    def __init__(self):
        self.registry = {}


    """ Registers a task making it available through the manager

    @param key: key for task
    @param task: task instance
    """
    def register(self, key, task):
        self.registry[key] = task


    """ deregisters a task, stopping it and removing it from the manager

    @param key: key for task
    @param task: task instance
    """
    def deregister(self, key, task):
        # stop the task in case its running
        task.stop()

        # remove the task from the registry
        del registry[key]


    """ Iterates through a task and its children to build an array display information

    @param task: Task to process
    @param tasklist: Array to append data onto.  Uused for recursion.
    """
    def processTask(self, task, tasklist=None, parent=False):
        # initial call wont have an area yet
        if tasklist==None:
            tasklist = []

        #turn the task into a tuple
        processedTask = [task.id, parent, task.msg]

        #add that task to the list
        tasklist.append(processedTask)

        #add all children if the task is a container
        if isinstance(task,TaskContainer):
            for subtask in task.subtasks:
                self.processTask(subtask.task, tasklist, task.id)

        return tasklist


    """ Iterates through a task and its children to build an array of status information
    @param task: Task to process
    @param tasklist: Array to append data onto.  Uused for recursion.
    """
    def processTaskProgress(self, task, tasklist=None):
        # initial call wont have an area yet
        if tasklist==None:
            tasklist = []

        #turn the task into a tuple
        processedTask = {'id':task.id, 'status':task.status(), 'progress':task.progress(), 'msg':task.progressMessage()}

        #add that task to the list
        tasklist.append(processedTask)

        #add all children if the task is a container
        if isinstance(task,TaskContainer):
            for subtask in task.subtasks:
                self.processTaskProgress(subtask.task, tasklist)

        return tasklist


    """ 
    listTasks - builds a list of tasks
    @param keys: filters list to include only these tasks
    """
    def listTasks(self, keys=None):
        message = {}
        # show all tasks by default
        if keys == None:
            keys = self.registry.keys()

        for key in keys:
            message[key] = self.processTask(self.registry[key])

        return message

    """  
    builds a dictionary of progresses for tasks
    @param keys: filters list to include only these tasks
    """
    def progress(self, keys=None):
        print "================"
        message = {}

        # show all tasks by default
        if keys == None:
            keys = self.registry.keys()

        # store progress of each task in a dictionary
        for key in keys:
            progress = self.processTaskProgress(self.registry[key])
            message[key] = {
                'status':progress
            }

        return message

    """ Starts a task

    @param key: key to the task to start
    """
    def start(self, key):
        self.registry[key].start()
        return '1'

    """ Stops a task

    @param key: key to the task to stop
    """
    def stop(self, key):
        self.registry[key].stop()
        return '1'
