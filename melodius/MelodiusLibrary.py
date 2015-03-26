import mutagen

from gi.repository import Gio
import os, sqlite3

class MelodiusLibrary:
    def __init__(self):
        conn = sqlite3.connect(os.path.join( os.getenv("HOME"), ".melodius", "library.db" ))
        c = conn.cursor()
        self.library = []
        for (path, title, artist, album, track, length, rating) in c.execute('''SELECT * FROM library ORDER BY artist, album, track'''):
            self.library.append([path, title, artist, album, track, length, rating])
        c.close()
        conn.close()
        
    def __len__(self):
        return len(self.library)
        
    def get_tracks(self):
        return self.library
        
    def add_folder(self, folder):
        conn = sqlite3.connect(os.path.join( os.getenv("HOME"), ".melodius", "library.db" ))
        c = conn.cursor()
        for root, dirs, files in os.walk(folder):
            for file in files:
                filename = os.path.join( root, file )
                try:
                    mutagen_file = mutagen.File(filename)
                    if mutagen_file:
                        path = filename.replace('\'', '\\\'').replace('\"', '\\\"')
                        path = path.encode()
                        
                        try:
                            track = mutagen_file['TRCK'].text[0].replace('\'', '\\\'').replace('\"', '\\\"')
                            if '/' in track:
                                track = track.split('/')[0]
                            track = int(track)
                        except KeyError:
                            track = -1
                        try:
                            title = mutagen_file['TIT2'].text[0].replace('\'', '\\\'').replace('\"', '\\\"')
                        except KeyError:
                            title = ''
                        try:
                            artist = mutagen_file['TPE1'].text[0].replace('\'', '\\\'').replace('\"', '\\\"')
                        except KeyError:
                            artist = 'Unknown'
                        try:
                            album = mutagen_file['TALB'].text[0].replace('\'', '\\\'').replace('\"', '\\\"')
                        except KeyError:
                            album = 'Unknown'
                        length = mutagen_file.info.length
                        length_seconds = int(length)
                        length_minutes = int(length_seconds/60)
                        length_seconds = length_seconds - (length_minutes*60)
                        length_hours = int(length_minutes/60)
                        length_minutes = length_minutes - (length_hours * 60)
                        
                        length_seconds = str(length_seconds)
                        if len(length_seconds) == 1:
                            length_seconds = "0" + length_seconds
                        length_minutes = str(length_minutes)
                        if len(length_minutes) == 1:
                            length_minutes = "0" + length_minutes
                        length_hours = str(length_hours)
                        if len(length_hours) == 1:
                            length_hours = "0" + length_hours
                        
                        length_string = "%s:%s:%s" % (length_hours, length_minutes, length_seconds)
                        rating = 0
                        if title:
                            command = '''INSERT INTO library VALUES ("%s", "%s", "%s", "%s", "%s", "%s", %s)''' % (str(path), str(title), str(artist), str(album), str(track), length_string, rating)
                            c.execute(command)
                except Exception as err:
                    print ("Encounted exception processing %s" % filename)
                    print ("Exception: %s" % err)
                    print(type(path))
        conn.commit()
        c.close()
        conn.close()
        
    def remove_folder(self, folder_path):
        # Connect to sqlite db
        conn = sqlite3.connect(os.path.join( os.getenv("HOME"), ".melodius", "library.db" ))
        c = conn.cursor()
        
        # Get folders from settings
        settings = Gio.Settings("net.launchpad.melodius")
        folders = settings['folders']
        
        # Remove this folder
        folders.remove(folder_path)
        
        # Begin new library
        new_library = []
        for item in self.library:
            path = item[0]
            keep = False
            
            # Make sure file is not included by another library folder
            for folder in folders:
                if path.startswith(folder):
                    keep = True
                    new_library.append(item)
                    break
                    
            # Remove the item from the database
            if not keep:
                command = '''DELETE FROM library WHERE path = "%s"''' % (path)
                c.execute(command)
                
        # Close the db connection
        conn.commit()
        c.close()
        conn.close()
        
        # Save the new library
        self.library = new_library
