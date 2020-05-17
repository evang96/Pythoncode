import hashlib
from pyfingerprint.pyfingerprint import PyFingerprint

#This tries to initialize the sensor

def verify():
        
    try:
        f = PyFingerprint('/dev/ttyUSB0', 57600, 0xFFFFFFFF, 0x00000000) #Fingerprint runs to check fprint

        if ( f.verifyPassword() == False ):
            raise ValueError('Incorrect fingerprint, try again!') #If the wrong fingerprint is used, login won't proceed, refresh

    except Exception as e:
        print('The fingerprint could not be initialized!')
        print('Exception message: ' + str(e))
        exit(1) #Finished

    # Checks to see if fingerprint is already registered
    print('Currently used templates: ' + str(f.getTemplateCount()) +'/'+ str(f.getStorageCapacity()))

    #Tries to search the finger
    try:
        print('Waiting for finger...')

        #Finger is read
        while ( f.readImage() == False ):
            pass

        ## Converts read image to characteristics and stores it in charbuffer 1
        f.convertImage(0x01)

        ## Searchs template
        result = f.searchTemplate()

        positionNumber = result[0]
        accuracyScore = result[1]

        if ( positionNumber == -1 ): #If the fingerprint is not found it will display -1
            print('No match found!')
            return 0
            #exit(0)
        else:
            print('Found template at position #' + str(positionNumber))
            print('The accuracy score is: ' + str(accuracyScore))

        ## OPTIONAL stuff
        ##

        ## Loads the found template to charbuffer 1
        f.loadTemplate(positionNumber, 0x01)

        ## Downloads the characteristics of template loaded in charbuffer 1
        characterics = str(f.downloadCharacteristics(0x01)).encode('utf-8')

        ## Hashes characteristics of template
        print('SHA-2 hash of template: ' + hashlib.sha256(characterics).hexdigest())
        return 1

    except Exception as e:
        print('Operation failed!')
        print('Exception message: ' + str(e))
        exit(1)

#verify()