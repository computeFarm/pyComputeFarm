// This code has been adapted from the example contained near the end of:
//  https://www.openssl.org/docs/man3.0/man3/EVP_get_digestbyname.html
// Adapted on 2022-11-14
// see also: https://stackoverflow.com/a/5125110
// gcc -o hashCheck hashCheck.c -lcrypto

#include <stdio.h>
#include <string.h>
#include <openssl/evp.h>

#define HASH_CHECK_EXT ".hashCheck"
#define IN_FILE_BUFFER_SIZE 4096
#define FALSE 0
#define TRUE 1

int usage(void) {
  printf("usage: hashCheck <<pathToFileToCheck>>\n");
  printf("\n");
  printf("options:\n");
  printf("  -h  Print this help message\n");
  printf("  -q  Do not output any messages\n");
  return 2;
}

int main(int argc, char *argv[]) {
  const char* inFilePath = NULL;
  int verbose = TRUE;
  int curArg = 1;
  while (curArg < argc) {
    if (strcmp(argv[curArg], "-q") == 0) {
    	verbose = FALSE;
    	curArg++;
    } else if (strcmp(argv[curArg], "-h") == 0) return usage();
    else if (argv[curArg][0] != '-') {
      inFilePath = argv[curArg];
      break;
    } else {
    	printf("No path to file to check provided\n");
    	return usage();
    }
  }
  if (inFilePath == NULL) return usage();

  if (verbose) printf("Checking the sha512 hash of [%s]\n", inFilePath);

  FILE *inFile = fopen(inFilePath, "rb");
  if (inFile == NULL) {
  	printf("Could not open [%s]\n", inFilePath);
  	return 2;
  }

  int checkFilePathLen = strlen(inFilePath) + strlen(HASH_CHECK_EXT) + 10;
  char* checkFilePath = calloc(checkFilePathLen, sizeof(char));
  strncpy(checkFilePath, inFilePath, checkFilePathLen);
  strncat(checkFilePath, HASH_CHECK_EXT, checkFilePathLen - strlen(inFilePath));
  FILE *checkFile = fopen(checkFilePath, "rb");

  unsigned char checkValue[64];
  memset(checkValue, 0, 64*sizeof(unsigned char));
  if (checkFile != NULL) {
  	int bytesRead = fread(&checkValue, sizeof(unsigned char), 64, checkFile);
  	if (bytesRead != 64) {
  		memset(checkValue, 0, 64*sizeof(unsigned char));
  	}
  }
  if (checkFile) fclose(checkFile);
  EVP_MD_CTX *mdctx;
  mdctx = EVP_MD_CTX_new();

  const EVP_MD *md;
  md = EVP_get_digestbyname("sha512");
  if (md == NULL) {
    printf("Could not create an OpenSLL sha512 digest\n");
  	fclose(inFile);
    return 2;
  }
  EVP_DigestInit_ex2(mdctx, md, NULL);

  char buffer[IN_FILE_BUFFER_SIZE];
  while (TRUE) {
    memset(buffer, 0, IN_FILE_BUFFER_SIZE*sizeof(char));
    int bytesRead = fread(&buffer, sizeof(char), IN_FILE_BUFFER_SIZE, inFile);
    if (bytesRead == 0) break ;
    EVP_DigestUpdate(mdctx, buffer, bytesRead);
  }
  fclose(inFile);
  unsigned char md_value[EVP_MAX_MD_SIZE];
  unsigned int md_len;
  EVP_DigestFinal_ex(mdctx, md_value, &md_len);
  EVP_MD_CTX_free(mdctx);

  int checkOK = TRUE;
  for (unsigned int i = 0; i < md_len; i++ ) {
    if (checkValue[i] != md_value[i]) {
    	checkOK = FALSE;
    	break;
    }
  }

  if (checkOK) {
    if (verbose) {
    	printf("No differences found\n");
    }
    return 0;
  }

  checkFile = fopen(checkFilePath, "wb");
  if (checkFile == NULL) {
  	printf("Could not open [%s] to write hash value\n", checkFilePath);
  	fclose(inFile);
  	return 2;
  }

  int bytesWritten = fwrite(md_value, sizeof(unsigned char), 64, checkFile);
  if (bytesWritten != 64) {
  	printf("Could not write the hash value to [%s]\n", checkFilePath);
  	fclose(checkFile);
  	fclose(inFile);
  }

  if (verbose) {
    printf("\nCheck is : ");
    for (unsigned int i = 0; i < md_len; i++)
      printf("%02x", checkValue[i]);
    printf("\n");
    printf("Digest is: ");
    for (unsigned int i = 0; i < md_len; i++)
      printf("%02x", md_value[i]);
    printf("\n");
  }
  return 1;
}
