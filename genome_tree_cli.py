#!/usr/bin/env python
import argparse
import sys
import genome_tree_backend as backend
import getpass
import random
import os

import profiles

def ErrorReport(msg):
    sys.stderr.write(msg)
    sys.stderr.flush()

def NewPasswordPrompt(GenomeDatabase):
    autogenerated = False
    password = getpass.getpass("Enter new password (leave blank to auto-generate):")
    if password == '':
        password = GenomeDatabase.GenerateRandomPassword()
        autogenerated = True
    if not autogenerated and (password != getpass.getpass("Confirm password:")) :
        ErrorReport("Passwords don't match.\n")
        return None
    return (password, autogenerated)

def CreateUser(GenomeDatabase, args):
    password_tuple = NewPasswordPrompt(GenomeDatabase)
    if password_tuple is not None:
        (password, autogenerated) = password_tuple
    else:
        return False
    GenomeDatabase.CreateUser(args.username, password, args.type)
    if autogenerated:
        print "Temporary password: " + password + "\n"
    print "User Created!\n"
    return True
        
def ModifyUser(GenomeDatabase, args):
    
    user_id = GenomeDatabase.GetUserIdFromUsername(args.username)
    
    password = None
    if args.password:
        password_tuple = NewPasswordPrompt(GenomeDatabase)
        if password_tuple is not None:
            (password, autogenerated) = password_tuple
        else:
            return False
        
    if GenomeDatabase.ModifyUser(user_id, password, args.type):
        if args.password and autogenerated:
            print "New temporary password: " + password + "\n"
        print "User Modified!"
        return True
    else:
        print GenomeDatabase.lastErrorMessage
        return False
        
def ShowUser(GenomeDatabase, args):
    pass
    
def DeleteUser(GenomeDatabase, args):
    pass

def AddFastaGenome(GenomeDatabase, args):
    genome_id = GenomeDatabase.AddFastaGenome(args.filename, args.name, args.description, "C")
    if genome_id is not None:
        GenomeDatabase.CalculateMarkersForGenome(genome_id)
        (tree_id, name, description, owner_id) = GenomeDatabase.GetGenomeInfo(genome_id)
        print "Added %s as %s\n" % (name, tree_id)

def AddManyFastaGenomes(GenomeDatabase, args):
    fh = open(args.batchfile, "rb")
    added_ids = []
    for line in fh:
        splitline = line.split("\t")
        genome_id = GenomeDatabase.AddFastaGenome(splitline[0].rstrip(), splitline[1].rstrip(), splitline[2].rstrip(), "C")
        if genome_id is not None:
            GenomeDatabase.CalculateMarkersForGenome(genome_id)
            added_ids.append(genome_id)
        else:
            ErrorReport(GenomeDatabase.lastErrorMessage + "\n")
    for genome_id in added_ids:
        (tree_id, name, description, owner_id) = GenomeDatabase.GetGenomeInfo(genome_id)
        print "Added %s as %s\n" % (name, tree_id)

def ExportFasta(GenomeDatabase, args):
    genome_id = GenomeDatabase.GetGenomeId(args.tree_id)
    if not genome_id:
        ErrorReport("Genome not found.\n")
        return None
    if args.output_fasta is None:
        print GenomeDatabase.ExportGenomicFasta(genome_id)
    elif args.output_fasta:
        GenomeDatabase.ExportGenomicFasta(genome_id, args.output_fasta)

def DeleteGenome(GenomeDatabase, args):
    genome_id = GenomeDatabase.GetGenomeId(args.tree_id)
    if genome_id is not None:
        if GenomeDatabase.DeleteGenome(genome_id) is None:
            ErrorReport(GenomeDatabase.lastErrorMessage + "\n")

def SearchGenomes(GenomeDatabase, args):
    user_id = None
    if args.owner is None:
        user_id = GenomeDatabase.currentUser.getUserId()
    elif args.owner != '-1':
        user_id = GenomeDatabase.GetUserIdFromUsername(args.owner)
        if user_id is None:
            ErrorReport(GenomeDatabase.lastErrorMessage)
            return None
    return_array = GenomeDatabase.SearchGenomes(args.name, args.description, args.list_id, user_id)
    
    if not return_array:
        return None

    format_str = "%12.12s %50.50s %15.15s %25.25s %30.30s"
    print format_str % ("Tree ID","Name","Owner","Added","Description")
    for (tree_id, name, username, date_added, description) in return_array:
        print format_str % (tree_id, name, username, date_added, description)

def ShowGenome(GenomeDatabase, args):
    pass
        
def ShowGenomeSources(GenomeDatabase, args):
    print "Current genome sources:"
    for (source_id, name) in GenomeDatabase.GetGenomeSources():
        print "    " + name
        
def CreateGenomeList(GenomeDatabase, args):
    genome_source = None
    if args.source:
        genome_source = GenomeDatabase.GetGenomeSourceIdFromName(args.source)
        if genome_source is None:
            print GenomeDatabase.lastErrorMessage()
            return False
    genome_list = list()
    
    fh = open(args.filename, 'rb')
    for line in fh:
        line = line.rstrip()
        genome_id = GenomeDatabase.GetGenomeId(line, genome_source)
        if genome_id:
            genome_list.append(genome_id)
        else:
            ErrorReport("Unable to find genome: %s, ignoring\n" % (line,))
    fh.close()
    
    GenomeDatabase.CreateGenomeList(genome_list, args.name, args.description,
                                    GenomeDatabase.currentUser.getUserId(),
                                    not args.public)
    
def CloneGenomeList(GenomeDatabase, args):
    genome_source = None
    if args.source:
        genome_source = GenomeDatabase.GetGenomeSourceIdFromName(args.source)
        if genome_source is None:
            print GenomeDatabase.lastErrorMessage()
            return False
    genome_list = list()
    
    fh = open(args.filename, 'rb')
    for line in fh:
        line = line.rstrip()
        genome_id = GenomeDatabase.GetGenomeId(line, genome_source)
        if genome_id:
            genome_list.append(genome_id)
        else:
            ErrorReport("Unable to find genome: %s, ignoring\n" % (line,))
    fh.close()
    
    GenomeDatabase.CreateGenomeList(genome_list, args.name, args.description,
                                    GenomeDatabase.currentUser.getUserId(),
                                    not args.public)

def DeleteGenomeList(GenomeDatabase, args):
    if not args.force:
        if GenomeDatabase.DeleteGenomeList(args.list_id, args.force):
            if raw_input("Are you sure you want to delete this list? ")[0].upper() != 'Y':
                return False
    GenomeDatabase.DeleteGenomeList(args.list_id, True)

def CreateTreeData(GenomeDatabase, args):
    list_ids = args.list_ids.split(",")
    genome_id_set = set()
    if args.tree_ids:
        extra_ids = [GenomeDatabase.GetGenomeId(x) for x in args.tree_ids.split(",")]
        genome_id_set = genome_id_set.union(set(extra_ids))
    for list_id in list_ids:
        temp_genome_list = GenomeDatabase.GetGenomeIdListFromGenomeListId(list_id)
        if temp_genome_list:
            genome_id_set = genome_id_set.union(set(temp_genome_list))
        
    if len(genome_id_set) > 0:
        GenomeDatabase.MakeTreeData(list(genome_id_set), args.profile, args.out_dir)

def ShowAllGenomeLists(GenomeDatabase, args):
    if args.self_owned:
        genome_lists = GenomeDatabase.GetGenomeLists(GenomeDatabase.currentUser.getUserId())
    else:
        genome_lists = GenomeDatabase.GetGenomeLists()
    
    print "ID\tName\tOwner\tDesc\n"
    for (list_id, name, description, user) in genome_lists:
        print "\t".join((str(list_id), name, user, description)),"\n"

def CalculateMarkers(GenomeDatabase, args):
    genome_id = GenomeDatabase.GetGenomeId(args.tree_id)
    GenomeDatabase.CalculateMarkersForGenome(genome_id)
    
if __name__ == '__main__':
    
    # create the top-level parser
    parser = argparse.ArgumentParser(prog='genome_tree_cli.py')
    parser.add_argument('-u', dest='login_username', required=True,
                        help='Username to log into the database')
    parser.add_argument('--dev', dest='dev', action='store_true',
                        help='Run in developer mode')
    
    subparsers = parser.add_subparsers(help='Sub-Command Help', dest='subparser_name')
    
# -- User management subparsers

# -------- Create users
    
    parser_createuser = subparsers.add_parser('CreateUser',
                                              help='Create user help')
    parser_createuser.add_argument('--user', dest = 'username',
                                   required=True, help='Username of the created user')
    parser_createuser.add_argument('--type', dest = 'type',
                                   required=True, help='User type')
    parser_createuser.set_defaults(func=CreateUser)
    
# -------- Modify users
    
    parser_modifyuser = subparsers.add_parser('ModifyUser', help='Modify user help')
    parser_modifyuser.add_argument('--user', dest = 'username',
                                   required=True, help='Username of the user')
    parser_modifyuser.add_argument('--type', dest = 'type', help='User type')
    parser_modifyuser.add_argument('--password', dest = 'password',
                                   action = 'store_true', help='User type')
    parser_modifyuser.set_defaults(func=ModifyUser)
    
# -------- Show users
    
    parser_showuser = subparsers.add_parser('ShowUser', help='Show user help')
    parser_showuser.add_argument('--user', dest = 'username',
                                required=True, help='Username of the user')
    parser_showuser.set_defaults(func=ShowUser)
    
# -------- Delete users
    
    parser_deleteuser = subparsers.add_parser('DeleteUser', help='Delete user help')
    parser_deleteuser.add_argument('--user', dest = 'username',
                                   required=True, help='Username of the user to delete')
    parser_deleteuser.add_argument('--force', dest = 'force', action='store_true',
                                   help='Do not prompt for confirmation')
    parser_deleteuser.set_defaults(func=DeleteUser)
       
# -------- Genome management subparsers
    
    parser_addfastagenome = subparsers.add_parser('AddFastaGenome',
                                    help='Add a genome to the tree from a Fasta file')
    parser_addfastagenome.add_argument('--file', dest = 'filename',
                                       required=True, help='FASTA file to add')
    parser_addfastagenome.add_argument('--name', dest = 'name',
                                       required=True, help='Name of the genome')
    parser_addfastagenome.add_argument('--description', dest = 'description',
                                       required=True, help='Brief description of the genome')
    parser_addfastagenome.set_defaults(func=AddFastaGenome)
    
    
    parser_addmanyfastagenomes = subparsers.add_parser('AddManyFastaGenomes',
                                    help='Add a genome to the tree from a Fasta file')
    parser_addmanyfastagenomes.add_argument('--batchfile', dest = 'batchfile',
                                    required=True, help='Add genomes en masse with a batch file (one genome per line, tab separated in 3 columns (filename,name,desc))')
    parser_addmanyfastagenomes.set_defaults(func=AddManyFastaGenomes)
    
# --------- Export FASTA Genome
    
    parser_exportfasta = subparsers.add_parser('ExportFasta',
                                    help='Export a genome to a FASTA file')
    parser_exportfasta.add_argument('--tree_id', dest = 'tree_id',
                                    required=True, help='Tree IDs')
    #parser_exportfasta.add_argument('--genome_list_id', dest = 'genome_list_id',
    #                                help='Name of the genome')
    parser_exportfasta.add_argument('--output', dest = 'output_fasta',
                                    help='Output the genome to a FASTA file')
    parser_exportfasta.set_defaults(func=ExportFasta)
    
# --------- Delete FASTA Genome

    parser_deletegenome = subparsers.add_parser('DeleteGenome',
                                    help='Delete a genome from the database')
    parser_deletegenome.add_argument('--tree_id', dest = 'tree_id',
                                    help='Tree IDs')
    parser_deletegenome.set_defaults(func=DeleteGenome)

# --------- Genome Searching

    parser_searchgenome = subparsers.add_parser('SearchGenomes',
                                    help='Add a genome to the tree from a Fasta file')
    parser_searchgenome.add_argument('--name', dest = 'name',
                                       help='Search for genomes containing this name')
    parser_searchgenome.add_argument('--description', dest = 'description',
                                       help='Search for genomes containing this description')
    parser_searchgenome.add_argument('--list_id', dest = 'list_id',
                                       help='Show all genomes in this list')
    parser_searchgenome.add_argument('--owner', dest = 'owner', nargs='?', default='-1',
                                       help='Search for genomes owned by this username. ' +
                                      'With no parameter finds genomes owned by the current user')
    parser_searchgenome.set_defaults(func=SearchGenomes) 
    
# --------- Show Genome Sources
    
    parser_showgenomesources = subparsers.add_parser('ShowGenomeSources',
                                help='Show the sources of the genomes')
    parser_showgenomesources.set_defaults(func=ShowGenomeSources)
    
# --------- Create A Genome List

    parser_creategenomelist = subparsers.add_parser('CreateGenomeList',
                                        help='Create a genome list from a list of accessions')
    parser_creategenomelist.add_argument('--file', dest = 'filename',
                                       required=True, help='File containing list of accessions')
    parser_creategenomelist.add_argument('--source', dest = 'source',
                                       help='Source of the accessions listed in the file')
    parser_creategenomelist.add_argument('--name', dest = 'name',
                                       required=True, help='Name of the genome list')
    parser_creategenomelist.add_argument('--description', dest = 'description',
                                       required=True, help='Brief description of the genome list')
    parser_creategenomelist.add_argument('--public', dest = 'public', default=False,
                                       action='store_true', help='Make the list visible to all users.')
    parser_creategenomelist.set_defaults(func=CreateGenomeList)
    
# --------- Clone A Genome List

    parser_clonegenomelist = subparsers.add_parser('CloneGenomeList',
                                        help='Create a genome list from a list of accessions')
    parser_clonegenomelist.add_argument('--list_id', dest = 'list_id', type=int,
                                       required=True, help='File containing list of accessions')
    parser_clonegenomelist.add_argument('--name', dest = 'name',
                                       required=True, help='Name of the genome list')
    parser_clonegenomelist.add_argument('--description', dest = 'description',
                                       required=True, help='Brief description of the genome list')
    parser_clonegenomelist.add_argument('--public', dest = 'public', default=False,
                                       action='store_true', help='Make the list visible to all users.')
    parser_clonegenomelist.set_defaults(func=CloneGenomeList)


# --------- Delete A Genome List

    parser_deletegenomelist = subparsers.add_parser('DeleteGenomeList',
                                        help='Create a genome list from a list of accessions')
    parser_deletegenomelist.add_argument('--list_id', dest = 'list_id', type=int,
                                       required=True, help='ID of the genome list to delete')
    parser_deletegenomelist.add_argument('--force', dest = 'force', action='store_true',
                                        help='Do not prompt for confirmation of deletion')
    parser_deletegenomelist.set_defaults(func=DeleteGenomeList)

# -------- Show All Genome Lists

    parser_showallgenomelists = subparsers.add_parser('ShowAllGenomeLists',
                                        help='Create a genome list from a list of accessions')
    parser_showallgenomelists.add_argument('--owned', dest = 'self_owned',  default=False,
                                        action='store_true', help='Only show genome lists owned by you.')
    parser_showallgenomelists.set_defaults(func=ShowAllGenomeLists)

# -------- Generate Tree Data
    
    parser_createtreedata = subparsers.add_parser('CreateTreeData',
                                        help='Generate data to create genome tree')
    parser_createtreedata.add_argument('--genome_list_ids', dest = 'list_ids',
                                        required=True, help='Create genome tree data from these lists (comma separated).')
    parser_createtreedata.add_argument('--tree_ids', dest = 'tree_ids',
                                        help='Add these tree_ids to the output, useful for including outgroups (comma separated).')
    parser_createtreedata.add_argument('--output', dest = 'out_dir',
                                        required=True, help='Directory to output the files')
    parser_createtreedata.add_argument('--profile', dest = 'profile',
                                        help='Marker profile to use (default: %s)' % (profiles.ReturnDefaultProfileName(),))
    #parser_generatetreedata.add_argument('--prefix', dest = 'prefix',
    #                                   help='Prefix of output files ()')
    parser_createtreedata.set_defaults(func=CreateTreeData)
     
# -------- Marker management subparsers

    parser_calculatemarkers = subparsers.add_parser('CalculateMarkers',
                                help='Calculate markers')
    parser_calculatemarkers.add_argument('--tree_id', dest = 'tree_id',
                                         required=True,  help='Tree ID')
    parser_calculatemarkers.set_defaults(func=CalculateMarkers)

    args = parser.parse_args()
    
    # Initialise the backend
    GenomeDatabase = backend.GenomeDatabase()
    if args.dev:
        GenomeDatabase.MakePostgresConnection(10000)
    else:
        GenomeDatabase.MakePostgresConnection()
        
    # Login
    User = GenomeDatabase.UserLogin(args.login_username,
                                    getpass.getpass("Enter your password (%s):" %
                                                    (args.login_username,) ))    
    if not User:
        ErrorReport("Database login failed. The following error was reported:\n" +
                    "\t" + GenomeDatabase.lastErrorMessage)
        sys.exit(-1)

    args.func(GenomeDatabase, args)


