import sys
import os
import re
import subprocess
import tempfile
import time
import random
import string

import psycopg2 as pg
import bcrypt

#---- User Class

class User(object):
    def __init__(self, userId, userName, typeId):
        self.userId = userId
        self.userName = userName
        self.typeId = typeId
    
    def getUserName(self):
        return self.userName
    
    def getUserId(self):
        return self.userId
    
    def getTypeId(self):
        return self.typeId

#--- Main Genome Database Object

class GenomeDatabase(object):
    def __init__(self):
        self.conn = None
        self.currentUser = None
        self.lastErrorMessage = None
        self.phylosift_bin = "/srv/whitlam/bio/apps/sw/phylosift/genome_tree_phylosift/bin/phylosift"

#-------- General Functions
    
    def ReportError(self, msg):
        self.lastErrorMessage = str(msg) + "\n"
        
#-------- Database Connection Management

    def MakePostgresConnection(self):
        self.conn = pg.connect("dbname=genome_tree host=/tmp/")
        
    def ClosePostgresConnection(self):
        self.conn.close()
        self.conn = None
    
    def IsPostgresConnectionActive(self):
        if self.conn is not None:
            cur = self.conn.cursor()
            try:
                cur.execute("SELECT * from genomes")
            except:
                return False
            cur.close()
            return True
        else:
            return False

#-------- User Login Management
    
    def GenerateRandomPassword(self, length=8):
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choice(chars) for x in range(8))
        
    def GenerateHashedPassword(self, password):
        return bcrypt.hashpw(password, bcrypt.gensalt())
    
    def CheckPlainTextPassword(self, password, hashed_password):
        return bcrypt.hashpw(password, hashed_password) == hashed_password
    
    def UserLogin(self, username, password):
        if not self.IsPostgresConnectionActive():
            self.ReportError("Unable to establish database connection")
            return None
   
        cur = self.conn.cursor()
        query = "SELECT id, password, type_id FROM users WHERE username = %s"
        cur.execute(query, [username])
        result = cur.fetchone()
        cur.close()
        if result:
            (userid, hashed, type_id) = result
            if self.CheckPlainTextPassword(password, hashed):
                self.currentUser = User(result[0], username, result[2])
                return User
            else:
                self.ReportError("Incorrect password")
        else:
            self.ReportError("User not found")
        return None

#-------- User Management

    def CreateUser(self, username, password, userTypeId):
        
        if not self.IsPostgresConnectionActive():
            self.ReportError("Unable to establish database connection")
            return False
        
        if not self.currentUser:
            self.ReportError("You need to be logged in to create a user")
            return False
        
        if userTypeId <= self.currentUser.getTypeId():
            self.ReportError("Cannot create a user with same or higher level privileges")
            return False
        
        cur = self.conn.cursor()
        cur.execute("INSERT into users (username, password, type_id) " +
                    "VALUES (%s, %s, %s) ", (username,
                                             self.GenerateHashedPassword(password),
                                             userTypeId))
        self.conn.commit()
        
        return True
    
    def ModifyUser(self, user_id, password=None, userTypeId=None):
        
        if not self.IsPostgresConnectionActive():
            self.ReportError("Unable to establish database connection.")
            return False
        
        if not self.currentUser:
            self.ReportError("You need to be logged in to modify a user.")
            return False
        
        if userTypeId <= self.currentUser.getTypeId():
            self.ReportError("Cannot change a user to have the same or higher level privileges as you.")
            return False
        
        cur = self.conn.cursor()
        query = "SELECT user_id FROM users WHERE if = %s"
        cur.execute(query, [user_id])
        
        result = cur.fetchone()

        if not result:
            self.ReportError("Unable to find user id: " + user_id)
            return False            
        
        if password is not None:
            if not password:
                self.ReportError("You must specify a non-blank password.")
                return False
            else:
                cur.execute("UPDATE users SET password = %s WHERE id = %s", 
                    (Passwordify(password), user_id))
        
        if userTypeId is not None:
            cur.execute("UPDATE users SET userTypeId = %s WHERE id = %s", 
                    (userTypeId,  user_id))
        
        self.conn.commit()
        return True
    
#    def DeleteUser(self, user_id):  ----- TODO: Add a function for deleting users
        
#-------- Genome List Management

    def CreateGenomeList(self, genome_list, name, description, owner_id, private):
        
        cur = self.conn.cursor()
        
        randid = random.randint(0,16**8)
        temp_table_name = "ids_%x" % (randid,)
        tree_ids = self.GenomeListTextCtrl.GetValue().split("\n")
        
        query = "INSERT INTO genome_lists (name, description, owner_id, private) VALUES (%s, %s, %s, %s) RETURNING id"
        cur.execute(query, (name, description, owner_id, private))
        (genome_list_id, ) = cur.fetchone()
        
        query = "INSERT INTO genome_list_contents (list_id, genome_id) VALUES (%s, %s)"
        cur.executemany(query, [(genome_list_id, x) for x in genome_list])
        
        self.conn.commit()
        
        return True
    
    def CheckGenomeList(self):
        
        conn = GetTopParent(self).conn
        cur = GetTopParent(self).cur
        
        # Remove empty rows
        insert_params = [(x,) for x in tree_ids if x]
    
        cur.execute("CREATE TEMP TABLE %s (genome_id text)" % (temp_table_name,) )
        cur.executemany("INSERT INTO %s (genome_id) VALUES (%%s)" % (temp_table_name,), insert_params)
        conn.commit()
        
        if self.DatabaseIDRadioButton.GetValue():
            source_id = self.sources[self.SourceDropDown.GetSelection()][0]
            query = "SELECT id FROM genomes WHERE genome_source_id = %%s AND id_at_source IN (SELECT genome_id from %s)" % (temp_table_name,)
            cur.execute(query, (source_id,))
            genome_ids = [x[0] for x in cur.fetchall()]
            
            query = "SELECT genome_id from %s EXCEPT SELECT id_at_source from genomes WHERE genome_source_id = %%s" % (temp_table_name,)
            cur.execute(query, (source_id,))
            missing_ids = [x[0] for x in cur.fetchall()]
            
        else:
            cur.execute("SELECT id FROM genomes WHERE tree_id IN (SELECT genome_id from %s)" % (temp_table_name,))
            genome_ids = [x[0] for x in cur.fetchall()]
            
            cur.execute("SELECT genome_id from %s EXCEPT SELECT tree_id from genomes" % (temp_table_name,))
            missing_ids = [x[0] for x in cur.fetchall()]
            
        if len(missing_ids) > 0:
            ErrorLog("Warning: The following entered IDs were not found in the " +
                     "database and have been excluded from the list:\n %s \n" % ("\n".join(missing_ids),))

        return genome_ids

#-------- Genome Management
    
    def CheckGenomeExists(self, genome_id):
        
        cur = self.conn.cursor()
        
        cur.execute("SELECT id " +
            "FROM genomes " +
            "WHERE id = %s ", [genome_id])
        
        if cur.fetchone():
            return True
        else:
            return False
        
    def GetGenomeOwner(self, genome_id):
        
        cur = self.conn.cursor()
        
        cur.execute("SELECT owner_id " +
            "FROM genomes " +
            "WHERE id = %s ", [genome_id])
        
        result = cur.fetchone()
        if not result:
            self.ReportError("Unable to find genome_id: " + genome_id )
            return None
        
        (owner_id,) = result
        return owner_id
        
        
    def GetGenomeId(self, tree_id=None, source_name=None, id_at_source=None):
        
        cur = self.conn.cursor()
        
        return_id = None
        
        if tree_id and (source_name or id_at_source):
            self.ReportError("Cannot specify both a tree id and source specific params")
            return False
        
        if tree_id is not None:
            cur.execute("SELECT id " +
                        "FROM genomes " +
                        "WHERE tree_id = %s ", [tree_id])
            
            result = cur.fetchone()
            if result is None:
                self.ReportError("Unable to find tree id: " + tree_id)
                return None
            
            (genome_id, ) = result
            
            return genome_id
            
        if (source_name is not None) or (source_name is not None):
            if (source_name is not None) and (source_name is not None):
                
                # Check that the source actually exists
                cur.execute("SELECT id " +
                            "FROM genome_sources " +
                            "WHERE name = %s ", [source_name])
                result = cur.fetchone()
                
                if not result:
                    self.ReportError("No genome source found named '%s'" % (source_name,))
                    return None
                
                (genome_source_id,) = result
                
                # Find the genome
                cur.execute("SELECT id " +
                            "FROM genomes,  " +
                            "WHERE id_at_source = %s " +
                            "AND source_id = %s", [id_at_source, genome_source_id])
            
                result = cur.fetchone()
                if result is None:
                    self.ReportError("Unable to find tree id: " + tree_id)
                    return None
                
                (genome_id, ) = result
                
                return genome_id

    def GetGenomeSources(self):
        cur = self.conn.cursor()
        
        cur.execute("SELECT id, name FROM genome_sources")
        
        return cur.fetchall()
    
    def FindPhylosiftMarkers(self, phylosift_bin, fasta_file):
        result_dir = tempfile.mkdtemp()
        return_dict = dict()
        subprocess.call([phylosift_bin, "search", "--besthit",
                                        "--output="+ result_dir, fasta_file])
        subprocess.call([phylosift_bin, "align", "--besthit",
                                        "--output="+ result_dir, fasta_file])
        for (root, dirs, files) in os.walk(result_dir + "/alignDir"):
            for filename in files:
                match = re.search('^(PMPROK\d*).fasta$', filename)
                if match:
                    prefix = match.group(1)
                    marker_fasta = open(os.path.join(root, filename), "rb")
                    for (name, seq, qual) in readfq(marker_fasta):
                        if not len(seq):
                            break
                        if (seq.count('-') / float(len(seq))) > 0.5: # Limit to less than half gaps
                            break
                        return_dict[prefix] = seq
                        break # Only want best hit.
                    marker_fasta.close()
        subprocess.call(["rm", "-rf", result_dir])
        return return_dict

    def CalculateMarkersForGenome(self, genome_id):
        
        cur = self.conn.cursor()

        if not self.CheckGenomeExists(genome_id):
            self.ReportError("Unable to find genome_id: " + genome_id)
            return False
        
        destfile = tempfile.mkstemp()[1]
        
        self.ExportGenomicFasta(genome_id, destfile)
        
        markers = self.FindPhylosiftMarkers(self.phylosift_bin, destfile)
        
        for (marker_id, seq) in markers.items():
            cur.execute("INSERT into aligned_markers (genome_id, marker_id, dna, sequence) " + 
                        "(SELECT %s, markers.id, False, %s " +
                        "        FROM markers, databases " +
                        "        WHERE database_specific_id = %s " +
                        "        AND database_id = databases.id " +
                        "        AND databases.name = 'Phylosift')" ,
                        (genome_id, seq, marker_id))
        
        self.conn.commit()
        
        os.unlink(destfile)
        
#-------- Fasta File Management

    def ExportGenomicFasta(self, genome_id, destfile=None):
        
        cur = self.conn.cursor()
        
        cur.execute("SELECT genomic_fasta " +
                    "FROM genomes " +
                    "WHERE id = %s ", [genome_id])
        result = cur.fetchone()
        
        if result is None:
            return None
        (genomic_oid,) = result
        
        fasta_lobject = self.conn.lobject(genomic_oid, 'r')
        
        if destfile is None:
            return fasta_lobject.read()
        else:
            fasta_lobject.export(destfile)
        
        return True
    
    def AddFastaGenome(self, fasta_file, name, desc, id_prefix, source_id=None, id_at_source=None):
        
        cur = self.conn.cursor()
        
        match = re.search('^[A-Z]$', id_prefix)
        if not match:
            self.ReportError("Tree ID prefixes must be in the range A-Z")
            return False
        
        try:
            fasta_fh = open(fasta_file, "rb")
        except:
            self.ReportError("Cannot open Fasta file: " + fasta_file)
            return False
        fasta_fh.close()
        
        if not self.currentUser:
            self.ReportError("You need to be logged in to add a FASTA file.")
            return False
        
        query = "SELECT tree_id FROM genomes WHERE tree_id like %s order by tree_id desc;"
        cur.execute(query, (id_prefix + '%',))
        last_id = None
        for (tree_id,) in cur:
            last_id = tree_id
            break
        if (last_id is None):
            new_id = id_prefix + "00000001"
        else:
            new_id = id_prefix + "%08.i" % (int(last_id[1:]) + 1)
        
        if source_id is None:
            cur.execute("SELECT id FROM genome_sources WHERE name = 'user'")
            result = cur.fetchone()
            if not result:
                self.ReportError("Could not find 'user' genome source. Possible database corruption.")
                return False
            (source_id,) = result
            if id_at_source is not None:
                self.ReportError("You cannot specify an ID at an unspecified genome source.")
                return False
        
        if id_at_source is None:
            id_at_source = new_id

        initial_xml_string = 'XMLPARSE (DOCUMENT \'<?xml version="1.0"?><data></data>\')'
        cur.execute("INSERT INTO genomes (tree_id, name, description, metadata, owner_id, genome_source_id, id_at_source) "
            + "VALUES (%s, %s, %s, " + initial_xml_string + ", %s, %s, %s) "
            + "RETURNING id" , (new_id, name, desc, self.currentUser.getUserId(),
                                source_id, id_at_source))
        
        row_id = cur.fetchone()[0]
        
        fasta_lobject = self.conn.lobject(0, 'w', 0, fasta_file)
        
        cur.execute("UPDATE genomes SET genomic_fasta = %s WHERE id = %s",
                    (fasta_lobject.oid, row_id))
        
        fasta_lobject.close()
        
        self.conn.commit()
    
#----- Other Functions

def readfq(fp): # this is a generator function
    """https://github.com/lh3/"""
    last = None # this is a buffer keeping the last unprocessed line
    while True: # mimic closure; is it a bad idea?
        if not last: # the first record or a record following a fastq
            for l in fp: # search for the start of the next record
                if l[0] in '>@': # fasta/q header line
                    last = l[:-1] # save this line
                    break
        if not last: break
        name, seqs, last = last[1:].split()[0], [], None
        for l in fp: # read the sequence
            if l[0] in '@+>':
                last = l[:-1]
                break
            seqs.append(l[:-1])
        if not last or last[0] != '+': # this is a fasta record
            yield name, ''.join(seqs), None # yield a fasta record
            if not last: break
        else: # this is a fastq record
            seq, leng, seqs = ''.join(seqs), 0, []
            for l in fp: # read the quality
                seqs.append(l[:-1])
                leng += len(l) - 1
                if leng >= len(seq): # have read enough quality
                    last = None
                    yield name, seq, ''.join(seqs); # yield a fastq record
                    break
            if last: # reach EOF before reading enough quality
                yield name, seq, None # yield a fasta record instead
                break
    